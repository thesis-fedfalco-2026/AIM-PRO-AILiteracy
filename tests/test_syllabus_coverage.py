"""Source-action coverage rejects missing practice without fixing a unit count."""

import hashlib
import json
import unittest
from unittest.mock import patch

from aimpro.retrieval import SelectedExcerpt, SourceQuery, SourceSelectionSummary
from aimpro.lead import ReviewError
from aimpro.syllabus import ATTEMPTS, SyllabusDraft, accepted, checked_syllabus, generate
from aimpro.syllabus_coverage import CoverageRequirement, UnitCoverage, validate_requirements
from tests.syllabus_fixtures import Curator, Reviewer, source, syllabus


def requirements(data):
    unit = syllabus(data).units[0]
    practice = unit.source_practice_ids[0]
    values = (
        ('demonstrate', 'FACILITATOR', 'EXPLAIN', 'The adviser builds a payment-reminder prompt live',
         'Demonstrate constructing a prompt and make the prompting choices visible.'),
        ('construct', 'LEARNER', 'PRACTICE', 'write a prompt for their own business',
         'Participants construct their own first fictional business prompt.'),
        ('explain-choices', 'LEARNER', 'PRACTICE', 'explain two choices',
         'Participants explain two choices in the prompt they constructed.'),
    )
    return tuple(CoverageRequirement(key=key, source_target_id=unit.source_target_id,
        source_object_id=practice, source_field='inPractice', source_quote=quote,
        actor=actor, expected_intent=intent, required_action=action)
        for key, actor, intent, quote, action in values)


def grounded_coverage():
    data = source()
    evidence = data.corpus_evidence
    resource = evidence.resources[0]
    document = resource.documents[0]
    summary = SourceSelectionSummary(trace_sha256='synthetic-test-trace',
        queries=(SourceQuery(query=evidence.query, k=evidence.k),),
        documents=(SelectedExcerpt(resource_id=resource.identity, resource_version=resource.version,
            document_id=document.id, content_sha256=hashlib.sha256(document.text.encode()).hexdigest(),
            purpose='Synthetic prompting evidence.', limitations=('Synthetic source only.',)),),
        coverage_requirements=requirements(data))
    return data.model_copy(update={'corpus_evidence': evidence.model_copy(update={'selection': summary})})


def covered_syllabus(data):
    draft = syllabus(data)
    entries = tuple(UnitCoverage(requirement_key=r.key, planned_action=r.required_action)
                    for r in data.corpus_evidence.selection.coverage_requirements)
    return draft.model_copy(update={'units': (draft.units[0].model_copy(update={'coverage': entries}),)})


class SyllabusCoverageTest(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(name, side_effect=AssertionError('Coverage tests must stay offline'))
            blocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(blocked.assert_not_called)
        self.data = grounded_coverage()

    def test_observed_explain_only_failure_is_blocked_before_separate_lead(self):
        draft = syllabus(self.data)
        unit = draft.units[0].model_copy(update={'planned_intents': ('EXPLAIN',),
            'purpose': 'The teacher builds a prompt before participants write their own.'})
        curator = Curator(draft.model_copy(update={'units': (unit,)}))
        reviewer = Reviewer()
        with self.assertRaisesRegex(ReviewError, 'omits explicit source-action coverage'):
            generate(self.data, dispatcher=curator, lead=reviewer)
        # A draft refused by the checks is tried again (Chat 20), and never reaches the reviewer.
        self.assertEqual(len(curator.calls), ATTEMPTS)
        self.assertEqual(reviewer.calls, [])

    def test_coverage_labels_cannot_make_explain_cover_required_practice(self):
        draft = covered_syllabus(self.data)
        unit = draft.units[0].model_copy(update={'planned_intents': ('EXPLAIN',)})
        with self.assertRaisesRegex(ValueError, 'required target, practice or intent'):
            checked_syllabus(self.data, draft.model_copy(update={'units': (unit,)}))

    def test_one_combined_unit_covers_source_actions_without_assess_or_thresholds(self):
        draft = checked_syllabus(self.data, covered_syllabus(self.data))
        self.assertEqual(len(draft.units), 1)
        self.assertEqual(draft.units[0].planned_intents, ('EXPLAIN', 'PRACTICE'))
        self.assertNotIn('ASSESS', draft.units[0].planned_intents)

    def test_demonstration_and_practice_can_be_separate_ordered_units(self):
        draft = covered_syllabus(self.data)
        unit = draft.units[0]
        demonstration = unit.model_copy(update={'planned_intents': ('EXPLAIN',), 'coverage': unit.coverage[:1]})
        practice = unit.model_copy(update={'key': 'practice', 'purpose': 'Construct a prompt and explain choices.',
            'planned_intents': ('PRACTICE',), 'coverage': unit.coverage[1:]})
        checked_syllabus(self.data, draft.model_copy(update={'units': (demonstration, practice)}))

    def test_missing_unknown_and_duplicate_coverage_keys_are_rejected(self):
        draft = covered_syllabus(self.data)
        unit = draft.units[0]
        for entries in (unit.coverage[:-1], (*unit.coverage, unit.coverage[0]),
                (UnitCoverage(requirement_key='invented', planned_action='Unrelated action.'), *unit.coverage)):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                checked_syllabus(self.data, draft.model_copy(update={'units': (unit.model_copy(update={'coverage': entries}),)}))

    def test_requirements_reject_unknown_target_practice_field_quote_or_key(self):
        original = requirements(self.data)
        for changes in ({'source_target_id': 'future-target'}, {'source_object_id': 'unrelated'},
                        {'source_field': 'description'}, {'source_quote': 'Invented passing score 80 percent'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_requirements(self.data, (original[0].model_copy(update=changes),))
        with self.assertRaises(ValueError):
            validate_requirements(self.data, original * 2)

    def test_legacy_payloads_still_validate_and_do_not_serialize_empty_extensions(self):
        data = source()
        original = syllabus(data)
        serialized = original.model_dump(mode='json')
        self.assertTrue(all('coverage' not in unit for unit in serialized['units']))
        self.assertEqual(checked_syllabus(data, SyllabusDraft.model_validate(serialized)), original)
        summary = self.data.corpus_evidence.selection.model_copy(update={'coverage_requirements': ()})
        self.assertNotIn('coverage_requirements', summary.model_dump(mode='json'))

    def test_valid_labels_still_require_independent_semantic_review(self):
        draft = covered_syllabus(self.data)
        # Structure alone cannot tell whether this planned text actually covers
        # the action. A separate semantic verdict must still be able to reject it.
        entries = tuple(c.model_copy(update={'planned_action': 'Participants merely watch a finished example.'})
                        for c in draft.units[0].coverage)
        draft = draft.model_copy(update={'units': (draft.units[0].model_copy(update={'coverage': entries}),)})
        checked_syllabus(self.data, draft)
        reviewer = Reviewer()
        reviewer.value = reviewer.value.model_copy(update={'verdict': 'REJECT', 'source_alignment': False})
        _, last, _ = generate(self.data, dispatcher=Curator(draft), lead=reviewer)
        self.assertFalse(accepted(last))
        self.assertEqual(len(reviewer.calls), ATTEMPTS)
