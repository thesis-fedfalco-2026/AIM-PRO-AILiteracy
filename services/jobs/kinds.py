"""Job kinds: one per existing generator and Curator command, named as the CLI command.

A job command names exact inputs: the project generators take the
``GenerationCommand`` of ``learning generate-project-*``; the Curator takes an
AIM-PRO export by file name and SHA-256 in the worker's export directory, and
the grounding of ``learning generate-aimpro-syllabus``. Each kind runs the
existing ``LearningService`` method, which authorizes, replays a recorded
``request_id`` without building a model, and records a pending proposal or a
failure. Model and retrieval factories come from :class:`Resources`, which only
the worker holds.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Any, Callable, Literal, NamedTuple

from pydantic import Field, model_validator

from aimpro.generators import GenerationCommand
from learning.contracts import Record, Text


class Resources(NamedTuple):
    """What only the worker holds: the model and retrieval factories and the AIM-PRO export directory."""
    authoring: Callable[[], Any]
    search: Callable[[], Any] | None
    exports: Path | None


class AssessmentJob(Record):
    """The Evaluator: ``learning generate-project-assessments``."""
    kind: Literal['generate-project-assessments']
    command: GenerationCommand


class TeacherJob(Record):
    """The Teacher: ``learning generate-project-teacher``."""
    kind: Literal['generate-project-teacher']
    command: GenerationCommand


class TrainerJob(Record):
    """The Trainer: ``learning generate-project-trainer``."""
    kind: Literal['generate-project-trainer']
    command: GenerationCommand


class AimproExport(Record):
    """An AIM-PRO project export in the worker's export directory, at this exact SHA-256."""
    name: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json$')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class SyllabusJob(Record):
    """The Curator: ``learning generate-aimpro-syllabus``, grounded by a query or prepared sources."""
    kind: Literal['generate-aimpro-syllabus']
    project: AimproExport
    source_scope: Text
    query: Text | None = None
    prepared_sources: Text | None = Field(None, description='Exact completed source-preparation request id')
    k: int = Field(5, ge=1, le=20)
    scenario: Text = 'SCN01'
    competencies: Text = 'elena_usecase_competencies'
    root_id: Text | None = None

    @model_validator(mode='after')
    def one_grounding(self):
        if (self.query is None) == (self.prepared_sources is None):
            raise ValueError('A syllabus job needs either a query or prepared sources')
        return self


JobCommand = Annotated[AssessmentJob | TeacherJob | TrainerJob | SyllabusJob, Field(discriminator='kind')]


class JobKind(NamedTuple):
    """``run(service, context_id, subject_key, request_id, command, resources)`` returns the service's response."""
    name: str
    command: type[Record]
    run: Callable[..., Any]


def _project(method):
    def run(service, context_id, subject_key, request_id, job, resources):
        return getattr(service, method)(context_id, subject_key, job.command, request_id=request_id,
                                        authoring_factory=resources.authoring)
    return run


def export_path(resources: Resources, export: AimproExport) -> Path:
    """The export file, refused unless it exists unchanged at the version the job names."""
    path = None if resources.exports is None else Path(resources.exports) / export.name
    if path is None or not path.is_file():
        raise ValueError('The AIM-PRO export is not available to the worker')
    if hashlib.sha256(path.read_bytes()).hexdigest() != export.sha256:
        raise ValueError('The AIM-PRO export differs from the exact version named by the job')
    return path


def _syllabus(service, context_id, subject_key, request_id, job, resources):
    return service.generate_aimpro_syllabus(context_id, subject_key, export_path(resources, job.project),
        request_id=request_id, authoring_factory=resources.authoring, scenario=job.scenario,
        competencies=job.competencies, root_id=job.root_id, source_scope=job.source_scope, query=job.query,
        k=job.k, search_factory=resources.search if job.prepared_sources is None else None,
        prepared_sources=job.prepared_sources)


KINDS = {kind.name: kind for kind in (
    JobKind('generate-project-assessments', AssessmentJob, _project('generate_project_assessments')),
    JobKind('generate-project-teacher', TeacherJob, _project('generate_project_teacher')),
    JobKind('generate-project-trainer', TrainerJob, _project('generate_project_trainer')),
    JobKind('generate-aimpro-syllabus', SyllabusJob, _syllabus),
)}
