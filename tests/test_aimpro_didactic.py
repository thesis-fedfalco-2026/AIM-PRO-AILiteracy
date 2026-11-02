import unittest

from aimpro.didactic import checked_draft, generate
from aimpro.lead import prepare_input
from tests.aimpro_fixtures import TeachingLead, draft


class DidacticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = prepare_input()

    def test_draft_is_generated_and_reviewed_with_source_constraints(self):
        lead = TeachingLead(self.data)
        result = generate(self.data, lead=lead)
        self.assertEqual(result.kind, 'DIDACTIC_DRAFT')
        self.assertEqual(len(lead.calls), 2)
        self.assertIn('use fictional customer details only.', lead.calls[0][0])
        self.assertIn('missing', lead.calls[1][0])

    def test_semantic_rejection_or_uncertainty_stops_generation(self):
        for verdict in ('REJECT', 'UNCERTAIN'):
            with self.assertRaisesRegex(ValueError, 'semantic review'):
                generate(self.data, lead=TeachingLead(self.data, verdict=verdict))

    def test_unknown_target_or_practice_is_rejected(self):
        value = draft(self.data)
        for unit in (value.units[0].model_copy(update={'source_target_id': 'invented'}),
                     value.units[0].model_copy(update={'activities': (
                         value.units[0].activities[0].model_copy(update={'source_practice_ids': ('invented',)}),)})):
            with self.assertRaises(ValueError):
                checked_draft(self.data, value.model_copy(update={'units': (unit,)}))

    def test_fingerprint_and_duplicate_rubric_keys_are_rejected(self):
        value = draft(self.data)
        with self.assertRaises(ValueError):
            checked_draft(self.data, value.model_copy(update={'source_sha256': 'invented'}))
        activity = value.units[0].activities[1]
        activity = activity.model_copy(update={'criteria': (activity.criteria[0], activity.criteria[0])})
        unit = value.units[0].model_copy(update={'activities': (activity,)})
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            checked_draft(self.data, value.model_copy(update={'units': (unit,)}))

    def test_generation_respects_budget_before_calling_model(self):
        lead = TeachingLead(self.data)
        with self.assertRaisesRegex(ValueError, 'budget'):
            generate(self.data, lead=lead, max_context_chars=10)
        self.assertEqual(lead.calls, [])
