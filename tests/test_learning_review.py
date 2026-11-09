"""Pending proposals for the review inbox: exact payload, review payload key, no writes (S05)."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.policies import AuthorizationError
from learning.service import LearningService
from learning.store import LearningStore
from tests.authoring_cycle_fixtures import AUTH, DELIVERY_TWO, trusted_policy
from tests.seed import build_seed
from tests.store_backends import block_network, new_store_location, on_both_backends


@on_both_backends
class PendingProposalsTest(unittest.TestCase):
    def setUp(self):
        block_network(self, 'Pending proposal reads use no network')
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        location = new_store_location(self, temp.name, 'seed.sqlite')
        self.seed = build_seed(Path(temp.name) / 'seed', location)
        self.store = LearningStore(location)
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(), Mock())

    def test_lists_the_latest_awaiting_revision_with_its_exact_candidates_and_key(self):
        for context_id in (AUTH, DELIVERY_TWO):
            with self.subTest(context_id):
                pending = self.service.pending_proposals(context_id, 'admin')
                self.assertEqual(tuple(p.proposal.ref for p in pending), self.seed.pending_proposals[context_id])
                for item in pending:
                    stored = self.store.read(item.proposal.ref, owner=context_id)
                    self.assertEqual(item.proposal, stored)
                    self.assertEqual(item.candidates, proposal_candidates(self.store, stored))
                    self.assertEqual(item.review_payload_key, stored.fields['reviewPayloadKey'])

    def test_the_key_is_the_one_a_decision_records_and_decided_proposals_leave_the_list(self):
        [item] = self.service.pending_proposals(AUTH, 'admin')
        decision = self.service.decide(AUTH, 'admin', item.proposal.ref, 'APPROVE', 'Synthetic review of the exact payload')
        self.assertEqual(decision.fields['reviewedPayloadKey'], item.review_payload_key)
        self.assertEqual(self.service.pending_proposals(AUTH, 'admin'), ())

    def test_a_learner_only_subject_sees_no_proposal_as_in_show(self):
        self.assertEqual(self.service.pending_proposals(DELIVERY_TWO, 'learner'), ())
        shown = self.service.show(DELIVERY_TWO, 'learner')
        self.assertNotIn('ChangeProposal', {e['type'] for e in shown['entities']})
        with self.assertRaises(AuthorizationError):
            self.service.pending_proposals(AUTH, 'learner')

    def test_reading_pending_proposals_writes_nothing(self):
        before = self.store.table_digests()
        for context_id, subject in ((AUTH, 'admin'), (DELIVERY_TWO, 'admin'), (DELIVERY_TWO, 'learner')):
            self.service.pending_proposals(context_id, subject)
        self.assertEqual(self.store.table_digests(), before)


if __name__ == '__main__':
    unittest.main()
