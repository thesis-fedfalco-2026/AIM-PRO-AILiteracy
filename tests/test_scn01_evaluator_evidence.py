"""Offline consistency of the real, owner-approved SCN01 publication extract."""

import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from aimpro.generators import AssessmentDraft, GenerationVerdict
from learning.contracts import Entity


DIRECTORY = Path(__file__).resolve().parents[1] / 'docs/aimpro/evidence/scn01-evaluator'


def read(name):
    return json.loads((DIRECTORY / name).read_text())


class SCN01EvaluatorEvidenceTest(unittest.TestCase):
    def setUp(self):
        for name in ('socket.create_connection', 'socket.getaddrinfo', 'socket.socket.connect'):
            blocker = patch(name, side_effect=AssertionError('Evidence verification is offline'))
            blocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(blocked.assert_not_called)

    def test_portable_artifacts_match_original_extracted_hashes(self):
        for name, expected in read('artifact-sha256.json').items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest(), expected)

    def test_real_draft_is_typed_and_cites_only_retained_exact_excerpts(self):
        draft = AssessmentDraft.model_validate(read('assessment-draft.json'))
        provenance = read('provenance.json')
        self.assertEqual(draft.input_digest, provenance['generation_input_digest'])
        self.assertEqual([u.key for u in draft.units], [u['key'] for u in read('approved-syllabus.json')['units']])
        available = {(r['resource_id'], r['resource_version']): {d['id'] for d in r['documents']}
                     for r in read('source-ledger.json')['resources']}
        self.assertEqual(sum(len(d) for d in available.values()), 7)
        items = [i for u in draft.units for i in u.items]
        self.assertEqual(len(items), 4)
        self.assertEqual(sum(len(i.criteria) for i in items), 9)
        self.assertEqual(sum(len(c.levels) for i in items for c in i.criteria), 18)
        self.assertEqual(sum(len(i.stimuli) for i in items), 6)
        for item in items:
            self.assertEqual(item.intent, 'ASSESS')
            for citation in (*item.citations, *(c for s in item.stimuli for c in s.citations)):
                self.assertLessEqual(set(citation.document_ids), available[(citation.resource_id, citation.resource_version)])
        self.assertTrue(draft.gaps)

    def test_human_approval_and_application_are_distinct_from_lead_accept(self):
        lead = GenerationVerdict.model_validate(read('lead-review.json'))
        self.assertEqual(lead.verdict, 'ACCEPT')
        approval = read('owner-approval.json')
        decision = Entity.model_validate(approval['decision'])
        self.assertEqual(decision.type, 'HumanDecision')
        self.assertEqual(decision.fields['decision'], 'APPROVE')
        application = read('assessment-application.json')
        change = Entity.model_validate(application['change'])
        self.assertEqual(change.type, 'StateChange')
        self.assertEqual(application['approval_decision'], decision.ref.model_dump(mode='json'))
        self.assertEqual(json.loads(change.fields['authorizationBasis']), application['approval_decision'])
        self.assertEqual(change.fields['cause'], approval['approved_proposal'])
        self.assertEqual(change.fields['newVersion'], application['context']['version'])
        self.assertEqual(application['review_payload_key'], decision.fields['reviewedPayloadKey'])
        self.assertEqual(application['proposal_status'], 'APPLIED')
        self.assertTrue(application['verification']['assessment_selected_and_receipt_valid'])
        self.assertFalse(application['verification']['learner_runtime_entities_created'])
        self.assertTrue(read('manual-review-findings.json')['findings'])
        self.assertTrue(approval['documented_findings_preserved'])
        self.assertTrue(application['unresolved_findings_preserved'])
