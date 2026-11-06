"""Opt-in local archive regression; only a disposable SQLite copy is opened for writes.

Run: python -m tests.verify_scn01_teacher_offline --output /tmp/teacher-offline.json
No archived file is edited. Synthetic assets are discarded with the temporary DB.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import socket
import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aimpro.generation_state import GeneratedArtifact
from aimpro.generators import GenerationCommand, GenerationInput
from aimpro.teacher_contracts import TeacherPlan
from learning.decisions import proposal_candidates
from learning.generation import resolve_inputs
from learning.metamodel import load_contract
from learning.policies import TrustedPolicy
from learning.service import LearningService
from learning.store import LearningStore
from tests.generator_fixtures import SyntheticModels


CONTEXT, SUBJECT = 'scn01-selected-syllabus-2', 'syllabus-author'
NAMES = ('scn01-assessments-1', 'scn01-assessments-2', 'scn01-assessments-3-claude',
         'scn01-assessments-4-native-json', 'scn01-assessments-5-revision',
         'scn01-teacher-1', 'scn01-teacher-2-revision', 'scn01-teacher-3-complete-peer',
         'scn01-teacher-4-structured', 'scn01-teacher-5-compact-schema',
         'scn01-teacher-6-prompt-schema')


def forbidden(*args, **kwargs):
    raise AssertionError('Offline verification forbids network and live models')


def inventory(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def verify(root):
    before = inventory(root)
    latest = root / 'teacher' / NAMES[-1]
    results = {}
    with TemporaryDirectory() as directory, patch.object(socket, 'create_connection', forbidden), \
            patch.object(socket, 'getaddrinfo', forbidden), patch.object(socket.socket, 'connect', forbidden):
        database = Path(directory) / 'copy.sqlite'
        with sqlite3.connect(f'file:{latest / "state.sqlite"}?mode=ro', uri=True) as source, \
                sqlite3.connect(database) as destination:
            source.backup(destination)
        with LearningStore(database) as store:
            service = LearningService(store, load_contract(),
                TrustedPolicy.model_validate_json((latest / 'policy.json').read_text()), forbidden)
            changes = store.db.total_changes
            for name in NAMES:
                teacher = name.startswith('scn01-teacher')
                base = root / ('teacher' if teacher else 'evaluator') / name
                command = GenerationCommand.model_validate_json((base / (
                    'teacher-command.json' if teacher else 'assessment-command.json')).read_text())
                manifest = json.loads((base / 'transmission-manifest.json').read_text())
                method = service.generate_project_teacher if teacher else service.generate_project_assessments
                result = method(CONTEXT, SUBJECT, command, request_id=manifest['request_id'], authoring_factory=forbidden)
                assert result.model_dump(mode='json') == json.loads((base / 'response.json').read_text())
                results[manifest['request_id']] = result.kind
            assert store.db.total_changes == changes
            current_command = GenerationCommand.model_validate_json((latest / 'teacher-command.json').read_text())
            current, _ = resolve_inputs(service, service._context(CONTEXT, SUBJECT),
                'TEACHER_CONTENT', current_command)
            assert current == GenerationInput.model_validate_json((latest / 'generation-input.json').read_text())
            legacy_base = root / 'teacher' / 'scn01-teacher-3-complete-peer'
            legacy_command = GenerationCommand.model_validate_json((legacy_base / 'teacher-command.json').read_text())
            legacy, _ = resolve_inputs(service, service._context(CONTEXT, SUBJECT), 'TEACHER_CONTENT', legacy_command)
            assert legacy.digest == json.loads((legacy_base / 'transmission-manifest.json').read_text())['input_digest']
            command = legacy_command.model_copy(update={'teacher_plan': TeacherPlan()})
            data, _ = resolve_inputs(service, service._context(CONTEXT, SUBJECT), 'TEACHER_CONTENT', command)
            decision = store.read(data.inputs[0].receipt.decision, owner=CONTEXT)
            assert data.inputs[0].approved_review.reason == decision.fields['reason']
            original_decisions = store.owned(CONTEXT, 'HumanDecision')
            original_changes = store.owned(CONTEXT, 'StateChange')
            models = SyntheticModels()
            result = service.generate_project_teacher(CONTEXT, SUBJECT, command,
                request_id='offline-structured-synthetic-only', authoring_factory=models.factory)
            assert result.kind == 'PROPOSAL', result
            proposal = store.read(result.proposal_refs[0], owner=CONTEXT)
            package = GeneratedArtifact.model_validate_json(next(e for e in proposal_candidates(store, proposal)
                if e.type == 'Resource' and e.fields.get('title') == 'Proposed TEACHER_CONTENT package').fields['contentOrLocator'])
            assert package.format_version == 2 and package.inputs == data
            assert package.draft.approved_review_notes[0].reason == decision.fields['reason']
            assert models.calls == ['teaching-designer-structured', 'LEAD_REVIEW']
            changes = store.db.total_changes
            assert service.generate_project_teacher(CONTEXT, SUBJECT, command,
                request_id='offline-structured-synthetic-only', authoring_factory=forbidden) == result
            assert changes == store.db.total_changes
            assert store.owned(CONTEXT, 'HumanDecision') == original_decisions
            assert store.owned(CONTEXT, 'StateChange') == original_changes
            view = service.inspect_authoring_project(CONTEXT, SUBJECT, 'scn01-evaluator')
            assert view.receipt and not view.approval_error and not view.stale_dependencies
            assert all(a.receipt and not a.approval_error for a in view.artifacts)
            assert not any(a.kind == 'TEACHER_CONTENT' for a in view.manifest.artifacts)
            report = {'historical_results': results, 'historical_input_digest_unchanged': legacy.digest,
                'fourth_input_digest_unchanged': current.digest,
                'exact_project': view.project.model_dump(), 'exact_assessment': command.assessments[0].model_dump(),
                'historical_approval_decision': decision.ref.model_dump(),
                'verbatim_reason_sha256': sha256(decision.fields['reason'].encode()).hexdigest(),
                'receipts_and_freshness_valid': True, 'historical_replay_writes': 0,
                'new_format_version': package.format_version, 'renderer_version': package.draft.renderer_version,
                'synthetic_only_calls': models.calls, 'synthetic_proposal_pending_and_discarded': True,
                'synthetic_exact_replay_without_factory': True, 'new_human_decisions': 0, 'new_applications': 0,
                'live_model_calls': 0, 'network_forbidden': True, 'teacher_selected': False,
                'source_sha256': data.syllabus.source.source.source_sha256}
    assert inventory(root) == before
    return dict(report, original_archive_files_unchanged=len(before))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives', type=Path, default=Path('.cache/aimpro-examples'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.archives.resolve()):
        parser.error('--output must be outside the preserved archives')
    args.output.write_text(json.dumps(verify(args.archives.resolve()), indent=2) + '\n')
    print(args.output)
