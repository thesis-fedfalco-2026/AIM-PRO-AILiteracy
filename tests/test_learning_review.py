"""Review inbox (S05) and decisions on the payload the reviewer saw (S06)."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import learning.decisions
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.policies import AuthorizationError
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
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


@on_both_backends
class ExpectedKeyDecisionTest(unittest.TestCase):
    """``decide(..., expected_key=...)``: the decision covers exactly the revision and payload the reviewer saw."""

    REASON = 'Synthetic review of the exact payload'

    def setUp(self):
        block_network(self, 'Decisions use no network')
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        location = new_store_location(self, temp.name, 'seed.sqlite')
        build_seed(Path(temp.name) / 'seed', location)
        self.store = LearningStore(location)
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(), Mock())

    def latest(self, context_id, proposal):
        return next(p for p in self.store.owned(context_id, 'ChangeProposal') if p.id == proposal.id)

    def test_the_key_the_reviewer_saw_records_the_decision(self):
        [item] = self.service.pending_proposals(AUTH, 'admin')
        decision = self.service.decide(AUTH, 'admin', item.proposal.ref, 'APPROVE', self.REASON,
                                       expected_key=item.review_payload_key)
        self.assertEqual(decision.fields['reviewedPayloadKey'], item.review_payload_key)
        self.assertEqual(decision.fields['target'], item.proposal.ref.model_dump())
        self.assertEqual(self.latest(AUTH, item.proposal).fields['status'], 'APPROVED')

    def test_a_stale_key_is_a_conflict_and_records_nothing(self):
        [item] = self.service.pending_proposals(AUTH, 'admin')
        [other] = self.service.pending_proposals(DELIVERY_TWO, 'admin')
        before = self.store.table_digests()
        for key in (other.review_payload_key, item.review_payload_key[:-1] + '0', 'pending'):
            if key == item.review_payload_key:
                continue
            with self.subTest(key=key), self.assertRaises(StateConflict):
                self.service.decide(AUTH, 'admin', item.proposal.ref, 'APPROVE', self.REASON, expected_key=key)
        self.assertEqual(self.store.table_digests(), before)

    def test_a_revision_decided_since_loading_is_a_conflict_until_reloaded(self):
        [item] = self.service.pending_proposals(AUTH, 'admin')
        self.service.decide(AUTH, 'admin', item.proposal.ref, 'REJECT', 'Another reviewer decided first')
        before = self.store.table_digests()
        with self.assertRaises(StateConflict):
            self.service.decide(AUTH, 'admin', item.proposal.ref, 'APPROVE', self.REASON,
                                expected_key=item.review_payload_key)
        self.assertEqual(self.store.table_digests(), before)
        # Reloading gives the current revision; its payload key is unchanged by the decision.
        current = self.latest(AUTH, item.proposal)
        self.assertEqual(current.fields['reviewPayloadKey'], item.review_payload_key)
        decision = self.service.decide(AUTH, 'admin', current.ref, 'APPROVE', self.REASON,
                                       expected_key=current.fields['reviewPayloadKey'])
        self.assertEqual(decision.fields['target'], current.ref.model_dump())
        self.assertEqual(self.latest(AUTH, item.proposal).fields['status'], 'APPROVED')

    def test_without_an_expected_key_a_decision_on_the_original_revision_is_still_recorded(self):
        [item] = self.service.pending_proposals(AUTH, 'admin')
        self.service.decide(AUTH, 'admin', item.proposal.ref, 'APPROVE', self.REASON)
        revocation = self.service.decide(AUTH, 'admin', item.proposal.ref, 'REJECT', 'Synthetic revocation')
        self.assertEqual(revocation.fields['target'], item.proposal.ref.model_dump())
        self.assertEqual(self.latest(AUTH, item.proposal).fields['status'], 'REJECTED')

    def test_the_key_check_and_the_decision_share_one_write_transaction(self):
        [item] = self.service.pending_proposals(AUTH, 'admin')
        latest, seen = learning.decisions._latest, []
        def observed(store, target, owner):
            seen.append(store.in_transaction)
            return latest(store, target, owner)
        with patch('learning.decisions._latest', observed):
            self.service.decide(AUTH, 'admin', item.proposal.ref, 'APPROVE', self.REASON,
                                expected_key=item.review_payload_key)
        self.assertEqual(seen, [True])
        self.assertFalse(self.store.in_transaction)


if __name__ == '__main__':
    unittest.main()
