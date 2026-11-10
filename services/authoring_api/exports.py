"""Module ``exports``: upload an AIM-PRO project export to start a course (S09a).

The request body is the file, as received. The API checks it before keeping
anything: its size, that it is UTF-8 JSON in the jjodel megamodel format 1.0,
that its metamodels can be read, and that the chosen scenario and competency
catalogue resolve. A refused file leaves nothing behind and the answer names
the reason. An accepted file is stored unchanged in ``ALM_AIMPRO_EXPORTS``,
the directory the worker reads, as ``<sha256>.json``; a Curator job names it by
that name and digest. Findings against the generated contracts do not refuse a
file: the report returns them with the scenario's source diagnostics.

Uploading writes nothing in the ALM store and queues no job.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Path as PathParam, Query, Request
from pydantic import JsonValue
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from aimpro.contracts import Contracts
from aimpro.didactic import targets
from aimpro.lead import prepare_input
from aimpro.validation import validate_scenario
from learning.contracts import Record, Text
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, WRITE_ERRORS, context_reader, context_writer, open_context
from services.api_common.registry import ApiModule
from services.jobs.kinds import AimproExport


EMPTY = 'The file is empty'
NOT_JSON = 'The file is not UTF-8 JSON'
NOT_MEGAMODEL = 'The file is not a jjodel megamodel export, format 1.0'
NO_METAMODELS = 'The metamodels of the export cannot be read'
NO_SCENARIO = 'The scenario and the competency catalogue cannot be resolved in the export'
OTHER_BYTES = 'The export directory holds other bytes under this name'
# What the AIM-PRO readers raise on a file they cannot read.
UNREADABLE = (ValueError, KeyError, TypeError, AttributeError, IndexError, RecursionError)


class ExportReport(Record):
    """An accepted export: its name and digest for a Curator job, and what the scenario check found."""
    export: AimproExport
    size: int
    project_id: Text
    scenario: Text
    competencies: Text
    root_id: Text
    objects: int
    conforms: bool
    source_diagnostics: tuple[dict[str, JsonValue], ...]
    contract_findings: tuple[dict[str, JsonValue], ...]


# The fields a coverage requirement may quote (``aimpro.syllabus_coverage.CoverageRequirement``).
QUOTABLE = ('description', 'inPractice', 'rationale', 'contextDetails')


class ExportObject(Record):
    """An object of the export with the texts a coverage requirement may quote."""
    id: Text
    class_name: Text
    fields: dict[str, str]


class ExportTarget(ExportObject):
    """A learning target with its practices: the anchors of a coverage requirement."""
    practices: tuple[ExportObject, ...]


class ExportTargets(Record):
    """The learning targets of a stored export's scenario, for the coverage requirements of a source plan."""
    export: AimproExport
    scenario: Text
    competencies: Text
    root_id: Text
    targets: tuple[ExportTarget, ...]


def configure(app, settings) -> None:
    app.state.aimpro_exports = settings.aimpro_exports
    app.state.export_max_bytes = settings.export_max_bytes


def _authorize(request: Request, context_id: str, subject_key: str) -> None:
    with open_context(request, context_id) as service:
        service.authorize_jobs(context_id, subject_key)


async def _content(request: Request, limit: int) -> bytes:
    """The body, refused as soon as it is larger than ``limit``."""
    too_large = f'The file is larger than {limit} bytes'
    declared = request.headers.get('content-length', '')
    if declared.isdigit() and int(declared) > limit:
        raise ValueError(too_large)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise ValueError(too_large)
        chunks.append(chunk)
    return b''.join(chunks)


def model_names(data: dict) -> str:
    """The model names of an export, for a refusal that has to name the right scenario and catalogue."""
    definitions = data.get('definitions')
    models = definitions.get('models') if isinstance(definitions, dict) else None
    names = [m['metadata'].get('name') for m in models if isinstance(m, dict) and isinstance(m.get('metadata'), dict)] \
        if isinstance(models, list) else []
    names = sorted({name for name in names if isinstance(name, str) and name.strip()})
    return f'. Models in the export: {", ".join(names)}' if names else ''


def keep(directory: Path, content: bytes, scenario: str, competencies: str, root_id: str | None) -> ExportReport:
    """Check ``content`` and store it unchanged as ``<sha256>.json``; on any refusal nothing stays in ``directory``."""
    if not content:
        raise ValueError(EMPTY)
    try:
        data = json.loads(content.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ValueError(NOT_JSON) from None
    if not isinstance(data, dict) or data.get('format') != 'jjodel-megamodel' or data.get('formatVersion') != '1.0':
        raise ValueError(NOT_MEGAMODEL)
    digest = hashlib.sha256(content).hexdigest()
    target = Path(directory) / (digest + '.json')
    # The readers take a path; a temporary name no job can name holds the bytes while they are checked.
    temporary = Path(directory) / f'.upload-{uuid4().hex}.tmp'
    try:
        with temporary.open('xb') as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        try:
            Contracts(temporary)
        except UNREADABLE:
            raise ValueError(NO_METAMODELS) from None
        try:
            report = validate_scenario(temporary, scenario=scenario, competencies=competencies, root_id=root_id)
        except UNREADABLE:
            raise ValueError(NO_SCENARIO + model_names(data)) from None
        if report['source']['source_sha256'] != digest:
            raise HTTPException(409, 'The file changed while it was checked')
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != content:
                raise HTTPException(409, OTHER_BYTES) from None
    finally:
        temporary.unlink(missing_ok=True)
    source = report['source']
    return ExportReport(export=AimproExport(name=target.name, sha256=digest), size=len(content),
                        project_id=source['project_id'], scenario=scenario, competencies=competencies,
                        root_id=source['root_id'], objects=len(source['objects']),
                        conforms=report['conforms_to_generated_contracts'],
                        source_diagnostics=tuple(source['diagnostics']), contract_findings=tuple(report['findings']))


def _object(item) -> dict:
    fields = {name: item.attributes[name] for name in QUOTABLE
              if isinstance(item.attributes.get(name), str) and item.attributes[name].strip()}
    return {'id': item.id, 'class_name': item.class_name, 'fields': fields}


def export_targets(directory: Path, sha256: str, scenario: str, competencies: str,
                   root_id: str | None) -> ExportTargets:
    """The targets and practices of the stored export ``<sha256>.json``; 404 when it is not stored."""
    path = Path(directory) / (sha256 + '.json')
    if not path.is_file():
        raise HTTPException(404, 'No stored export with this SHA-256')
    try:
        data = prepare_input(path, scenario=scenario, competencies=competencies, root_id=root_id)
    except UNREADABLE:
        raise ValueError(NO_SCENARIO) from None
    if data.source.source_sha256 != sha256:
        raise HTTPException(409, OTHER_BYTES)
    index = {o.id: o for o in data.source.objects}
    # ``targets`` refuses a scenario without targets or practices with its fixed reason.
    found = targets(data)
    return ExportTargets(export=AimproExport(name=path.name, sha256=sha256), scenario=scenario,
                         competencies=competencies, root_id=data.source.root_id,
                         targets=tuple(ExportTarget.model_validate({**_object(index[target]), 'practices': [
                             _object(index[p]) for p in sorted(practices)]}) for target, practices in found.items()))


router = APIRouter(tags=['exports'])

FILE_BODY = {'requestBody': {'required': True, 'content': {
    'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}}


@router.post('/contexts/{context_id}/aimpro-exports', response_model=ExportReport, responses=WRITE_ERRORS,
             openapi_extra=FILE_BODY,
             summary='Upload an AIM-PRO project export: checked, then stored unchanged for a Curator job')
async def upload(context_id: str, request: Request,
                 scenario: Annotated[str, Query(min_length=1, max_length=200)] = 'SCN01',
                 competencies: Annotated[str, Query(min_length=1, max_length=200)] = 'elena_usecase_competencies',
                 root_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
                 principal: Principal = Depends(context_writer)):
    # The authority to propose is checked before the body is read.
    await run_in_threadpool(_authorize, request, context_id, principal.subject_key)
    state = request.app.state
    content = await _content(request, state.export_max_bytes)
    return await run_in_threadpool(keep, state.aimpro_exports, content, scenario, competencies, root_id)


@router.get('/contexts/{context_id}/aimpro-exports/{sha256}/targets', response_model=ExportTargets,
            responses=READ_ERRORS, summary='The learning targets and practices of a stored export, with quotable texts')
def read_targets(context_id: str, request: Request,
                 sha256: Annotated[str, PathParam(pattern=r'^[0-9a-f]{64}$')],
                 scenario: Annotated[str, Query(min_length=1, max_length=200)] = 'SCN01',
                 competencies: Annotated[str, Query(min_length=1, max_length=200)] = 'elena_usecase_competencies',
                 root_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
                 principal: Principal = Depends(context_reader)):
    _authorize(request, context_id, principal.subject_key)
    return export_targets(request.app.state.aimpro_exports, sha256, scenario, competencies, root_id)


MODULE = ApiModule('exports', router)
