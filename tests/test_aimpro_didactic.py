import json
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
        payload = json.loads(lead.calls[0][0].split('\nDATA\n', 1)[1])
        self.assertEqual(payload['allowed_practice_ids_by_target'], {
            'Pointer1792169221668_USER_96': ['Pointer1792169384659_USER_127']})
        self.assertNotIn('Pointer1792169376696_USER_122',
                         payload['allowed_practice_ids_by_target']['Pointer1792169221668_USER_96'])

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

    def test_missing_or_duplicate_supporting_material_is_rejected(self):
        value = draft(self.data)
        original = value.units[0].activities[0]
        for activity in (
            original.model_copy(update={'supporting_materials': ()}),
            original.model_copy(update={'supporting_materials': original.supporting_materials * 2}),
        ):
            unit = value.units[0].model_copy(update={'activities': (activity,)})
            lead = TeachingLead(self.data, value=value.model_copy(update={'units': (unit,)}))
            with self.assertRaisesRegex(ValueError, 'supporting material'):
                generate(self.data, lead=lead)
            self.assertEqual(len(lead.calls), 1)

    def test_accept_cannot_override_incomplete_assets_or_technical_activities(self):
        for flags in ({'supporting_materials_complete': False}, {'learner_activities_only': False}):
            lead = TeachingLead(self.data, **flags)
            with self.assertRaisesRegex(ValueError, 'semantic review'):
                generate(self.data, lead=lead)
            self.assertEqual(len(lead.calls), 2)

    def test_repeated_target_units_are_rejected_before_review(self):
        value = draft(self.data)
        lead = TeachingLead(self.data, value=value.model_copy(update={'units': value.units * 2}))
        with self.assertRaisesRegex(ValueError, 'exactly one generated unit'):
            generate(self.data, lead=lead)
        self.assertEqual(len(lead.calls), 1)

    def test_unit_materials_can_be_shared_without_conflicting_content(self):
        value = draft(self.data)
        first, second = value.units[0].activities
        second = second.model_copy(update={'required_material_keys': ('demo-transcript',)})
        unit = value.units[0].model_copy(update={'activities': (first, second)})
        self.assertEqual(checked_draft(self.data, value.model_copy(update={'units': (unit,)})).units[0], unit)
        conflict = first.supporting_materials[0].model_copy(update={'content': 'Different content'})
        second = second.model_copy(update={'supporting_materials': (conflict,)})
        unit = unit.model_copy(update={'activities': (first, second)})
        with self.assertRaisesRegex(ValueError, 'conflicting supporting material'):
            checked_draft(self.data, value.model_copy(update={'units': (unit,)}))
