import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from aimpro.audit import DEFAULT_PROJECT
from learning.contracts import make_entity
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore
from tests.aimpro_fixtures import TeachingLead
from tests.test_learning_context import policy


class AimproTraceTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / 'state.sqlite')
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), policy(), Mock())
        self.root = self.service.bootstrap('session', 'admin')
        lead = TeachingLead()
        self.response = self.service.generate_aimpro('session', 'admin', DEFAULT_PROJECT,
            request_id='generate', lead_factory=lambda: (lead, None))

    def export(self, subject='admin', project=DEFAULT_PROJECT):
        return self.service.export_aimpro_trace('session', subject, project)

    def test_pending_then_applied_history_retains_source_and_exact_decision_chain(self):
        pending = self.export()
        self.assertTrue(pending['candidates'])
        activity = next(r for r in pending['candidates'] if r['entity']['type'] == 'ActivityDefinition')
        self.assertEqual(activity['mapping'], 'SOURCE_LINKED')
        decision = self.service.decide('session', 'admin', self.response.proposal_refs[0], 'APPROVE', 'Reviewed draft')
        change = self.service.apply('session', 'admin', self.response.proposal_refs[0], 'apply')
        trace = self.export()
        records = trace['records']
        for ref in (decision.ref, change.ref):
            record = next(r for r in records if {k: r['entity'][k] for k in ('type', 'id', 'version')} == ref.model_dump())
            self.assertEqual(record['mapping'], 'SOURCE_LINKED')
        self.assertGreater(len([r for r in records if r['entity']['type'] == 'ChangeProposal']), 1)
        self.assertEqual(trace['diagnostics'], [])
        self.assertEqual(trace['runtime_representation']['Evaluation'], 'ALM_ONLY')
        self.assertFalse(any(r['entity']['type'] in {'LearningState', 'Evaluation'} for r in records))

    def test_export_is_deterministic_and_does_not_write_state_or_source(self):
        before = self.store.db.total_changes
        source_hash = hashlib.sha256(DEFAULT_PROJECT.read_bytes()).hexdigest()
        first = self.export()
        self.assertEqual(first, self.export())
        self.assertEqual(before, self.store.db.total_changes)
        self.assertEqual(source_hash, hashlib.sha256(DEFAULT_PROJECT.read_bytes()).hexdigest())
        self.assertEqual(first['source']['sha256'], source_hash)
        self.assertFalse(first['source_modified'])

    def test_learner_cannot_export_other_participants_history(self):
        with self.assertRaises(ValueError):
            self.export('learner')

    def test_changed_source_does_not_reuse_lineage(self):
        path = Path(self.temp.name) / 'changed.json'
        value = json.loads(DEFAULT_PROJECT.read_bytes())
        value['metadata']['project']['name'] = 'Different source snapshot'
        path.write_text(json.dumps(value))
        trace = self.export(project=path)
        self.assertTrue(any(d['code'] == 'SOURCE_MISMATCH' for d in trace['diagnostics']))
        self.assertEqual(trace['source']['objects'], [])
        self.assertTrue(all(r['mapping'] == 'ALM_ONLY' for r in trace['records']))

    def test_context_history_excludes_other_owner_and_unrelated_domain(self):
        other = make_entity('Topic', 'unrelated-topic', {'name': 'Unrelated', 'definition': 'Not in this context'})
        self.store.seed((other,))
        foreign = make_entity('Participant', 'foreign-participant', {'subjectKey': 'foreign', 'roles': ['LEARNER']})
        self.store.seed((foreign,), owner='foreign-context')
        encoded = json.dumps(self.export())
        self.assertNotIn('unrelated-topic', encoded)
        self.assertNotIn('foreign-participant', encoded)

    def test_realistic_synthetic_evidence_and_evaluation_keep_source_links_and_no_inferred_progress(self):
        from aimpro import demo
        from learning.contracts import EntityRef
        directory = Path(self.temp.name) / 'demo'
        demo.init(directory)
        demo.review_import(directory, confirm=True)
        demo.activate(directory, confirm=True)
        submitted = demo.submit(directory, demo.ROOT / 'examples/scn01/synthetic-attempt.txt', 'attempt')
        with demo.session(directory) as service:
            evidence = service.store.read(EntityRef.model_validate(submitted['evidence']), owner=demo.CONTEXT)
            context = service._context(demo.CONTEXT, demo.AUTHOR)
            activity = context.snapshot.get(evidence.fields['activity'])
            spec = context.snapshot.get(activity.fields['assessmentSpec'])
            rubric = context.snapshot.get(spec.fields['rubric'])
            evaluation = make_entity('Evaluation', 'synthetic-evaluation', {
                'context': context.snapshot.context.ref.model_dump(), 'evidence': [evidence.ref.model_dump()],
                'specification': spec.ref.model_dump(), 'mode': 'FORMATIVE',
                'result': 'Synthetic test only; no performance judgment inferred', 'reviewPayloadKey': 'pending',
                'criterionJudgments': [{'criterionKey': c['key'],
                    'evidenceRefs': [evidence.ref.model_dump()], 'reason': 'Not assessed in this test'}
                    for c in rubric.fields['criteria']]})
            # Retain an unapplied assessment candidate to test the review boundary.
            proposal = service.propose(demo.CONTEXT, demo.AUTHOR, (context.snapshot.context.ref,),
                                       (evaluation,), 'Synthetic evaluation export test')
            trace = service.export_aimpro_trace(demo.CONTEXT, demo.AUTHOR, DEFAULT_PROJECT)
            observed = next(r for r in trace['records'] if r['entity']['type'] == 'LearningEvidence')
            candidate = next(r for r in trace['candidates'] if r['entity']['type'] == 'Evaluation')
            self.assertEqual(observed['mapping'], 'SOURCE_LINKED')
            self.assertEqual(candidate['mapping'], 'SOURCE_LINKED')
            self.assertEqual(candidate['proposal'], proposal.ref.model_dump())
            self.assertEqual(trace['diagnostics'], [])
            self.assertEqual(service.store.read_context(demo.CONTEXT).fields['learningStates'], [])
            self.assertEqual(service.store.owned(demo.CONTEXT, 'Evaluation'), ())

    def test_cli_exports_json_without_constructing_an_orchestrator(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from learning.__main__ import main
        path = Path(self.temp.name) / 'policy.json'
        path.write_text(self.service.policy.model_dump_json())
        output = StringIO()
        with patch('learning.__main__._orchestrator', side_effect=AssertionError('No model')), redirect_stdout(output):
            code = main(['--db', str(Path(self.temp.name) / 'state.sqlite'), '--policy', str(path),
                '--context', 'session', '--subject', 'admin', 'export-aimpro-trace', str(DEFAULT_PROJECT)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['representation'], 'ALM_SIDECAR')
