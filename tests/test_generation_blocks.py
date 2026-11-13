"""Generation by blocks of units (S09d, issue #118): a large syllabus is written in several model responses."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import openai

from agent_system import events
from agent_system.deadline import expired
from aimpro.generation_state import GeneratedArtifact
from aimpro.generators import (ATTEMPTS, BLOCK_UNITS, CUT, CUT_SPLIT, NOT_ACCEPTED, SPLIT, TIMED_OUT,
                               GenerationInput)
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore
from tests.authoring_cycle_fixtures import AUTH, SimulatedAuthoring, trusted_policy
from tests.generator_fixtures import GENERATION_REJECTION, SyntheticModels
from tests.store_backends import block_network
from tests import test_authoring_generators as generators


DESIGNER = 'assessment-designer'
REVIEW = 'LEAD_REVIEW'


def package_of(saved):
    return GeneratedArtifact.model_validate_json(next(e for e in saved
        if e.type == 'Resource' and e.id.startswith('authoring-output:')).fields['contentOrLocator'])


def data_of(prompt):
    return json.loads(prompt.split('\nDATA\n')[1])


def number(data):
    """The block of a model input before any split: its first unit's place in the syllabus, by 12."""
    return [u.key for u in data.units].index(data.block.unit_keys[0]) // BLOCK_UNITS + 1


def blocks_of(result):
    return [(a.block, a.attempt, a.final, a.reused, a.review.verdict if a.review else a.check) for a in result.attempts]


class GenerationBlocksTest(unittest.TestCase):
    """A 48-unit syllabus: four blocks of 12 units, each judged on its own, then the assembled draft judged once."""

    command = generators.AuthoringGeneratorTest.command
    run_generator = generators.AuthoringGeneratorTest.run_generator
    accept = generators.AuthoringGeneratorTest.accept

    def setUp(self):
        block_network(self, 'Generator tests must not use the network')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / 'blocks.sqlite')
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(), Mock())
        self.service.bootstrap(AUTH, 'admin')
        self.author = SimulatedAuthoring(self.service)
        self.author.curator(units=48)
        self.models = SyntheticModels()
        self.factory = Mock(side_effect=self.models.factory)
        self.accept_verdict = self.models.verdict

    def test_a_48_unit_syllabus_is_written_in_four_blocks_and_the_assembled_draft_judged_once(self):
        self.assertEqual(BLOCK_UNITS, 12)
        log = events.MemoryEventLog()
        with events.run(log, request_id='assessment', context_id=AUTH):
            result = self.run_generator()
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW] * 4 + [REVIEW])
        # Block N writes its own 12 units and receives the accepted drafts of the blocks before it, as data.
        for n, (data, prompt) in enumerate(zip(self.models.inputs, self.models.prompts), 1):
            self.assertEqual((number(data), len(data.block.unit_keys)), (n, BLOCK_UNITS))
            self.assertEqual(len(data.target_units), BLOCK_UNITS)
            self.assertIn('PROJECT_AUTHORING_BLOCK', prompt.split('\nDATA\n')[0])
            previous = data_of(prompt).get('previous_blocks', [])
            self.assertEqual([len(p['units']) for p in previous], [BLOCK_UNITS] * (n - 1))
            self.assertEqual(data_of(prompt)['input_digest'], data.digest)
        keys = [u.key for d in self.models.inputs for u in d.target_units]
        self.assertEqual(len(set(keys)), 48)
        # The review of a block sees the full input and that block only; the final review sees the assembled draft.
        *block_reviews, final = [data_of(r) for r in self.models.reviews]
        for n, review in enumerate(block_reviews, 1):
            self.assertEqual(review['input']['block'], self.models.inputs[n - 1].block.model_dump(mode='json'))
            self.assertEqual(len(review['draft']['units']), BLOCK_UNITS)
            self.assertNotIn('previous_blocks', review)
        self.assertNotIn('block', final['input'])
        self.assertEqual([u['key'] for u in final['draft']['units']], keys)
        self.assertIn('PROJECT_AUTHORING_BLOCK_REVIEW', self.models.reviews[0])
        self.assertNotIn('PROJECT_AUTHORING_BLOCK_REVIEW', self.models.reviews[-1])
        self.assertEqual(blocks_of(result), [(n, 1, False, False, 'ACCEPT') for n in range(1, 5)] +
                         [(None, 1, True, False, 'ACCEPT')])
        progress = [e.data for e in log.events if e.type == 'block']
        self.assertEqual([(e['block'], e['blocks'], e['outcome']) for e in progress],
                         [(n, 4, 'ACCEPTED') for n in range(1, 5)])
        reviews = [e.data for e in log.events if e.type == 'review']
        self.assertEqual([(r['stage'], r.get('block')) for r in reviews],
                         [('PROJECT', n) for n in range(1, 5)] + [('PROJECT_FINAL', None)])
        # One proposal, carrying the final verdict, over the exact input of the request.
        package = package_of(self.accept(result))
        self.assertEqual(len(package.draft.units), 48)
        self.assertIsNone(package.inputs.block)
        self.assertEqual(package.draft.input_digest, package.inputs.digest)
        self.assertEqual(package.review, self.accept_verdict)

    def test_teacher_and_trainer_blocks_reach_their_proposals_with_materials_of_every_block(self):
        for role in ('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'):
            with self.subTest(role=role):
                package = package_of(self.accept(self.run_generator(role, request_id=role), role))
                self.assertEqual(len(package.draft.units), 48)
                if role != 'ASSESSMENT':
                    materials = [m.key for m in package.draft.materials]
                    self.assertEqual(len(materials), len(set(materials)))
                    self.assertEqual(len(materials), 48 * (3 if role == 'TEACHER_CONTENT' else 1))

    def test_a_block_refused_once_is_retried_alone_with_its_feedback(self):
        self.models.verdicts = [self.accept_verdict, GENERATION_REJECTION]
        result = self.run_generator()
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW] * 5 + [REVIEW])
        retry = self.models.prompts[2]
        self.assertIn('PROJECT_AUTHORING_RETRY', retry.split('\nDATA\n')[0])
        data = data_of(retry)
        self.assertEqual(data['input']['block'], self.models.inputs[1].block.model_dump(mode='json'))
        self.assertEqual(data['review_feedback'], {'review': GENERATION_REJECTION.model_dump(mode='json')})
        self.assertEqual(data['rejected_draft']['input_digest'], self.models.inputs[1].digest)
        self.assertEqual(len(data['previous_blocks']), 1)
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT'), (2, 1, False, False, 'REJECT'),
            (2, 2, False, False, 'ACCEPT'), (3, 1, False, False, 'ACCEPT'), (4, 1, False, False, 'ACCEPT'),
            (None, 1, True, False, 'ACCEPT')])

    def test_material_keys_of_an_earlier_block_are_refused_and_the_block_retried(self):
        self.accept(self.run_generator(), 'apply-output')
        first = len(self.models.inputs)
        refused = []

        def collide(data, draft):
            if number(data) != 2 or refused:
                return draft
            refused.append(number(data))
            # Reuse the first material key of block 1 for a material of block 2.
            taken = data.units[0].key + ':explanation'
            old = draft.materials[0].key
            unit = draft.units[0]
            item = unit.items[0].model_copy(update={'material_keys': tuple(
                taken if k == old else k for k in unit.items[0].material_keys)})
            return draft.model_copy(update={
                'materials': (draft.materials[0].model_copy(update={'key': taken}), *draft.materials[1:]),
                'units': (unit.model_copy(update={'items': (item,)}), *draft.units[1:])})
        self.models.transform = collide
        result = self.run_generator('TEACHER_CONTENT', request_id='teacher')
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual([number(d) for d in self.models.inputs[first:]], [1, 2, 2, 3, 4])
        self.assertEqual(blocks_of(result)[1], (2, 1, False, False, 'Material keys must be unique across blocks'))

    def refuse_once(self, block, change):
        """``change`` the first draft of ``block`` only."""
        changed = []

        def transform(data, draft):
            if number(data) != block or changed:
                return draft
            changed.append(block)
            return draft.model_copy(update={'units': change(draft.units)})
        self.models.transform = transform

    def test_missing_and_unrequested_units_are_named_by_syllabus_position_and_their_keys_fed_back(self):
        invented = None

        def change(units):
            nonlocal invented
            invented = units[0].model_copy(update={'key': 'invented-unit'})
            return (units[0], *units[3:], invented)
        self.refuse_once(2, change)
        result = self.run_generator()
        self.assertEqual(result.kind, 'PROPOSAL')
        check = ('The draft must cover each unit it was asked to write once, in the order of the syllabus: units 14 '
                 'and 15 of the syllabus are missing; 1 unit it was not asked to write was added.')
        self.assertEqual(blocks_of(result)[1], (2, 1, False, False, check))
        # The model's own keys never reach the author; the retry receives the keys, as data.
        retry = data_of(self.models.prompts[2])
        self.assertEqual(retry['review_feedback'], {'check': check})
        block = [u.key for u in self.models.inputs[1].target_units]
        self.assertEqual(retry['check_details'], {'expected_unit_keys': block, 'missing_unit_keys': block[1:3],
                                                  'unexpected_unit_keys': ['invented-unit']})

    def test_repeated_and_reordered_units_are_refused_in_words(self):
        self.refuse_once(1, lambda units: (*units, units[4]))
        self.assertEqual(blocks_of(self.run_generator())[0][4], 'The draft must cover each unit it was asked to '
                         'write once, in the order of the syllabus: 1 unit is written more than once.')
        self.refuse_once(1, lambda units: tuple(reversed(units)))
        command = self.command(requirements=('Another command.',))
        self.assertEqual(blocks_of(self.run_generator(command=command, request_id='reordered'))[0][4],
                         'The draft must cover each unit it was asked to write once, in the order of the syllabus: '
                         'its units are not in the order of the syllabus.')

    def test_a_block_the_review_agent_does_not_accept_is_kept_and_the_job_proposed_with_a_notice(self):
        self.assertEqual(NOT_ACCEPTED, 'The review agent did not accept every block or the assembled draft; the last '
                         'drafts that passed the checks are proposed with its assessments, for the teacher to decide.')
        self.models.verdicts = [self.accept_verdict] + [GENERATION_REJECTION] * ATTEMPTS
        log = events.MemoryEventLog()
        with events.run(log, request_id='assessment', context_id=AUTH):
            result = self.run_generator()
        # Owner decision of 13 November 2026: a flow ends with something for the teacher to decide.
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(result.notice, NOT_ACCEPTED)
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT')] +
                         [(2, n, False, False, 'REJECT') for n in range(1, ATTEMPTS + 1)] +
                         [(3, 1, False, False, 'ACCEPT'), (4, 1, False, False, 'ACCEPT'), (None, 1, True, False, 'ACCEPT')])
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW] * (3 + ATTEMPTS) + [REVIEW])
        progress = [(e.data['block'], e.data['outcome']) for e in log.events if e.type == 'block']
        self.assertEqual(progress, [(1, 'ACCEPTED'), (2, 'KEPT'), (3, 'ACCEPTED'), (4, 'ACCEPTED')])
        self.assertEqual(len(package_of(self.accept(result)).draft.units), 48)

    def test_a_final_review_that_is_not_accept_is_proposed_with_a_notice(self):
        self.models.verdicts = [self.accept_verdict] * 4 + [GENERATION_REJECTION]
        result = self.run_generator()
        self.assertEqual((result.kind, result.notice), ('PROPOSAL', NOT_ACCEPTED))
        self.assertEqual(blocks_of(result)[-1], (None, 1, True, False, 'REJECT'))
        # Every block was accepted and is reused by a new job over the same exact inputs.
        calls = len(self.models.calls)
        resumed = self.run_generator(request_id='assessment-again')
        self.assertEqual(self.models.calls[calls:], [REVIEW])
        self.assertEqual(blocks_of(resumed), [(n, 1, False, True, 'ACCEPT') for n in range(1, 5)] +
                         [(None, 1, True, False, 'ACCEPT')])
        self.assertIsNone(resumed.notice)
        # The proposal keeps the review agent's verdict for the teacher.
        self.assertEqual(package_of(self.accept(result)).review, GENERATION_REJECTION)

    def test_a_block_whose_drafts_all_fail_the_checks_is_written_in_two_halves(self):
        def invalid(data, draft):
            if number(data) == 2 and len(data.block.unit_keys) == BLOCK_UNITS:
                return draft.model_copy(update={'input_digest': 'invented'})
            return draft
        self.models.transform = invalid
        result = self.run_generator()
        self.assertEqual((result.kind, result.notice), ('PROPOSAL', None))
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW] + [DESIGNER] * ATTEMPTS + [DESIGNER, REVIEW] * 4 + [REVIEW])
        self.assertEqual([len(d.block.unit_keys) for d in self.models.inputs], [12, 12, 12, 12, 6, 6, 12, 12])

    def test_a_block_of_one_unit_whose_drafts_fail_the_checks_fails_the_job_and_a_new_job_resumes(self):
        before = self.store.owned(AUTH, 'ChangeProposal')
        self.models.transform = lambda data, draft: (draft.model_copy(update={'input_digest': 'invented'})
                                                     if number(data) == 2 else draft)
        result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(result.content, 'Authoring generation did not complete (Generated output does not identify '
                         'the exact host input snapshot); no accepted proposal was persisted.')
        # Block 2 of 12 units, then halves of 6, 3, 2 and 1: three drafts each.
        sizes = [len(d.block.unit_keys) for d in self.models.inputs[1:]]
        self.assertEqual(sizes, [n for n in (12, 6, 3, 2, 1) for _ in range(ATTEMPTS)])
        self.assertEqual(self.store.owned(AUTH, 'ChangeProposal'), before)
        self.models.transform = None
        calls = len(self.models.calls)
        resumed = self.run_generator(request_id='assessment-again')
        self.assertEqual(resumed.kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [DESIGNER, REVIEW] * 3 + [REVIEW])
        self.assertEqual(blocks_of(resumed)[0], (1, 1, False, True, 'ACCEPT'))

    def test_blocks_are_reused_only_over_the_same_exact_inputs(self):
        self.assertEqual(self.run_generator().kind, 'PROPOSAL')
        calls = len(self.models.calls)
        other = self.command(requirements=('Prefer case analyses.',))
        self.assertEqual(self.run_generator(command=other, request_id='other').kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [DESIGNER, REVIEW] * 4 + [REVIEW])

    def time_out(self, when):
        """Make the model calls for which ``when(data)`` holds reach their deadline, as an SDK wraps it."""
        sizes = []

        def transform(data, draft):
            sizes.append(len(data.block.unit_keys))
            if when(data):
                deadline = expired(httpx.Request('POST', 'https://model.invalid/v1/chat'), 600)
                raise RuntimeError('provider text that must not be shown') from deadline
            return draft
        self.models.transform = transform
        return sizes

    def test_a_block_whose_call_reaches_its_deadline_is_written_in_two_halves(self):
        self.assertEqual(SPLIT, 'A model call reached its time limit; the units of this block are written in two '
                         'smaller blocks')
        timed_out = []
        log = events.MemoryEventLog()

        def when(data):
            if number(data) == 2 and len(data.block.unit_keys) == BLOCK_UNITS and not timed_out:
                timed_out.append(data)
                return True
            return False
        sizes = self.time_out(when)
        with events.run(log, request_id='assessment', context_id=AUTH):
            result = self.run_generator()
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(sizes, [12, 12, 6, 6, 12, 12])
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW, DESIGNER] + [DESIGNER, REVIEW] * 4 + [REVIEW])
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT'), (2, 1, False, False, SPLIT)] +
                         [(n, 1, False, False, 'ACCEPT') for n in range(2, 6)] + [(None, 1, True, False, 'ACCEPT')])
        self.assertTrue(result.attempts[1].timed_out)
        self.assertFalse(any(a.timed_out for a in result.attempts if a is not result.attempts[1]))
        progress = [(e.data['block'], e.data['blocks'], e.data['outcome']) for e in log.events if e.type == 'block']
        self.assertEqual(progress, [(1, 4, 'ACCEPTED'), (2, 4, 'SPLIT')] + [(n, 5, 'ACCEPTED') for n in range(2, 6)])
        self.assertEqual(len(package_of(self.accept(result)).draft.units), 48)

    def test_a_block_of_one_unit_past_the_deadline_stops_the_request_and_keeps_the_accepted_blocks(self):
        sizes = self.time_out(lambda data: number(data) == 2)
        with self.assertLogs('agent_system', 'WARNING') as logs:
            result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(TIMED_OUT, 'A model call reached its time limit')
        self.assertEqual(result.content, 'Authoring generation did not complete (A model call reached its time '
                         'limit); no accepted proposal was persisted.')
        self.assertNotIn('provider text', '\n'.join(logs.output))
        # Block 2 of 12 units, then the first half each time: 6, 3, 2 and 1.
        self.assertEqual(sizes, [12, 12, 6, 3, 2, 1])
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT')] + [(2, 1, False, False, SPLIT)] * 4 +
                         [(2, 1, False, False, TIMED_OUT)])
        self.assertEqual([a.timed_out for a in result.attempts], [False] + [True] * 5)
        self.models.transform = None
        calls = len(self.models.calls)
        self.assertEqual(self.run_generator(request_id='assessment-again').kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [DESIGNER, REVIEW] * 3 + [REVIEW])

    def test_a_response_cut_at_its_length_limit_is_written_in_two_halves(self):
        self.assertEqual(CUT, "The model's response was cut at its length limit")
        self.assertEqual(CUT_SPLIT, CUT + '; the units of this block are written in two smaller blocks')
        cut = []

        def transform(data, draft):
            if number(data) == 1 and len(data.block.unit_keys) == BLOCK_UNITS and not cut:
                cut.append(data)
                raise RuntimeError('provider text') from openai.LengthFinishReasonError(
                    completion=SimpleNamespace(usage=None))
            return draft
        self.models.transform = transform
        result = self.run_generator()
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(blocks_of(result)[:3], [(1, 1, False, False, CUT_SPLIT), (1, 1, False, False, 'ACCEPT'),
                                                 (2, 1, False, False, 'ACCEPT')])
        self.assertTrue(result.attempts[0].truncated)
        self.assertEqual([len(d.block.unit_keys) for d in self.models.inputs], [12, 6, 6, 12, 12, 12])

    def test_a_block_of_one_unit_cut_at_its_length_limit_stops_the_request(self):
        def transform(data, draft):
            raise RuntimeError('provider text') from openai.LengthFinishReasonError(completion=SimpleNamespace(usage=None))
        self.models.transform = transform
        with self.assertLogs('agent_system', 'WARNING') as logs:
            result = self.run_generator()
        self.assertEqual(result.content, "Authoring generation did not complete (The model's response was cut at its "
                         "length limit); no accepted proposal was persisted.")
        self.assertNotIn('provider text', '\n'.join(logs.output))
        self.assertEqual([len(d.block.unit_keys) for d in self.models.inputs], [12, 6, 3, 2, 1])


class SmallSyllabusBlockTest(unittest.TestCase):
    """A syllabus of at most 12 target units is one block, and its assembled draft is still judged (owner decision)."""

    setUp = generators.AuthoringGeneratorTest.setUp
    command = generators.AuthoringGeneratorTest.command
    run_generator = generators.AuthoringGeneratorTest.run_generator
    accept = generators.AuthoringGeneratorTest.accept

    def test_one_block_is_judged_on_its_own_and_then_assembled(self):
        result = self.run_generator()
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW, REVIEW])
        self.assertEqual(len(self.models.inputs[0].block.unit_keys), 1)
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT'), (None, 1, True, False, 'ACCEPT')])

    def test_an_input_without_a_block_keeps_its_historical_shape(self):
        result = self.run_generator()
        data = self.models.inputs[0]
        whole = GenerationInput.model_validate({k: v for k, v in data.model_dump(mode='json').items() if k != 'block'})
        self.assertNotIn('block', whole.model_dump(mode='json'))
        package = package_of(self.accept(result))
        self.assertEqual(package.inputs, whole)
        attempts = [a.model_dump(mode='json') for a in result.attempts]
        self.assertEqual(attempts[0], {'attempt': 1, 'block': 1, 'check': None,
                                       'review': self.models.verdict.model_dump(mode='json')})
        self.assertEqual(attempts[1], {'attempt': 1, 'final': True, 'check': None,
                                       'review': self.models.verdict.model_dump(mode='json')})


if __name__ == '__main__':
    unittest.main()
