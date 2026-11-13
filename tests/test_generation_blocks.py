"""Generation by blocks of units (S09d, issue #118): a large syllabus is written in several model responses."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import httpx

from agent_system import events
from agent_system.deadline import expired
from aimpro.generation_state import GeneratedArtifact
from aimpro.generators import ATTEMPTS, BLOCK_UNITS, TIMED_OUT, GenerationInput
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
            self.assertEqual((data.block.index, data.block.count), (n, 4))
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
            self.assertEqual(review['input']['block']['index'], n)
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
        self.assertEqual(data['input']['block']['index'], 2)
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
            if data.block.index != 2 or refused:
                return draft
            refused.append(data.block.index)
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
        self.assertEqual([d.block.index for d in self.models.inputs[first:]], [1, 2, 2, 3, 4])
        self.assertEqual(blocks_of(result)[1], (2, 1, False, False, 'Material keys must be unique across blocks'))

    def refuse_once(self, block, change):
        """``change`` the first draft of ``block`` only."""
        changed = []

        def transform(data, draft):
            if data.block.index != block or changed:
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

    def test_a_block_whose_drafts_run_out_fails_and_a_new_job_resumes_after_the_accepted_blocks(self):
        before = self.store.owned(AUTH, 'ChangeProposal')
        self.models.verdicts = [self.accept_verdict] + [GENERATION_REJECTION] * ATTEMPTS
        result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(result.content, 'Authoring generation did not complete (Authoring output did not pass '
                         'separate Lead review); no accepted proposal was persisted.')
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT')] +
                         [(2, n, False, False, 'REJECT') for n in range(1, ATTEMPTS + 1)])
        self.assertEqual(self.models.calls, [DESIGNER, REVIEW] * (1 + ATTEMPTS))
        self.assertEqual(self.store.owned(AUTH, 'ChangeProposal'), before)
        self.assertEqual(self.service.project_generation_request(AUTH, 'admin', 'assessment'), result)
        # A new job with the same command on the same exact inputs reuses block 1 without a model call.
        calls = len(self.models.calls)
        resumed = self.run_generator(request_id='assessment-again')
        self.assertEqual(resumed.kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [DESIGNER, REVIEW] * 3 + [REVIEW])
        self.assertEqual([d.block.index for d in self.models.inputs[-3:]], [2, 3, 4])
        self.assertEqual(blocks_of(resumed)[0], (1, 1, False, True, 'ACCEPT'))
        self.assertEqual(len(package_of(self.accept(resumed)).draft.units), 48)

    def test_a_final_review_that_is_not_accept_fails_and_a_new_job_reuses_every_block(self):
        self.models.verdicts = [self.accept_verdict] * 4 + [GENERATION_REJECTION]
        result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(blocks_of(result)[-1], (None, 1, True, False, 'REJECT'))
        calls = len(self.models.calls)
        resumed = self.run_generator(request_id='assessment-again')
        self.assertEqual(resumed.kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [REVIEW])
        self.assertEqual(blocks_of(resumed), [(n, 1, False, True, 'ACCEPT') for n in range(1, 5)] +
                         [(None, 1, True, False, 'ACCEPT')])

    def test_blocks_are_reused_only_over_the_same_exact_inputs(self):
        self.models.verdicts = [self.accept_verdict] * 4 + [GENERATION_REJECTION]
        self.assertEqual(self.run_generator().kind, 'FAILURE')
        calls = len(self.models.calls)
        other = self.command(requirements=('Prefer case analyses.',))
        self.assertEqual(self.run_generator(command=other, request_id='other').kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [DESIGNER, REVIEW] * 4 + [REVIEW])

    def test_a_model_call_past_its_deadline_fails_with_a_fixed_text_and_keeps_the_accepted_blocks(self):
        def late(data, draft):
            if data.block.index == 2:
                deadline = expired(httpx.Request('POST', 'https://model.invalid/v1/chat'), 600)
                raise RuntimeError('provider text that must not be shown') from deadline
            return draft
        self.models.transform = late
        with self.assertLogs('agent_system', 'WARNING') as logs:
            result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(TIMED_OUT, 'A model call reached its time limit')
        self.assertEqual(result.content, 'Authoring generation did not complete (A model call reached its time '
                         'limit); no accepted proposal was persisted.')
        self.assertNotIn('provider text', '\n'.join(logs.output))
        self.assertEqual(blocks_of(result), [(1, 1, False, False, 'ACCEPT')])
        self.models.transform = None
        calls = len(self.models.calls)
        self.assertEqual(self.run_generator(request_id='assessment-again').kind, 'PROPOSAL')
        self.assertEqual(self.models.calls[calls:], [DESIGNER, REVIEW] * 3 + [REVIEW])


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
        self.assertEqual((self.models.inputs[0].block.index, self.models.inputs[0].block.count), (1, 1))
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
