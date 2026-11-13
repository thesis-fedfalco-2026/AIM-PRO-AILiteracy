"""Synthetic model responses behind the production registry and typed dispatcher."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from agent_system.authoring import AuthoringDispatcher
from agent_system.config import load_category_catalog, load_model_catalog
from agent_system.registry import AgentRegistry
from aimpro.generators import (CONTRACTS, AssessmentDraft, GenerationInput,
                               GenerationVerdict, TeacherDraft, TrainerDraft)
from tests.syllabus_fixtures import REJECT_ONCE


ROOT = Path(__file__).resolve().parents[1]


def synthetic_draft(data):
    if data.command.teacher_plan is not None:
        from tests.teacher_fixtures import structured_draft
        return structured_draft(data)
    citation = data.syllabus.artifact.draft.units[0].corpus_citations[0].model_dump(mode='json')
    units, materials = [], []
    for unit in data.target_units:
        outcomes = unit.node.fields['outcomes']
        item = {'key': 'prompt', 'outcomes': outcomes, 'citations': [citation]}
        if data.role == 'ASSESSMENT':
            item.update(intent='ASSESS', format='CRITERIA_BASED_PRODUCT',
                instruction='Submit a fictional business reminder prompt and explain two choices.',
                evidence_kind='CRITERIA_BASED_PRODUCT',
                evidence_requirement='A written fictional prompt identifying its task, audience and tone, with two explained choices.',
                criteria=[{'key': 'clarity', 'description': 'The task and fictional audience are identifiable.',
                    'outcomes': outcomes, 'levels': [
                        {'key': 'unclear', 'descriptor': 'The business task or fictional audience cannot be identified from the prompt.'},
                        {'key': 'clear', 'descriptor': 'The business task, fictional audience and desired tone are explicitly stated.'}]}])
        else:
            teaching = data.role == 'TEACHER_CONTENT'
            item.update(intent='EXPLAIN' if teaching else 'PRACTICE',
                instruction='Compare the weak and improved fictional reminder prompts.' if teaching else
                    'Complete the worksheet: write a fictional reminder prompt and explain two choices.',
                material_keys=[])
            assets = [
                ('EXPLANATION', 'A business prompt states the task, audience and tone. Naming these makes the requested response explicit.'),
                ('TRANSCRIPT', 'I start with “Write a reminder”. The audience is missing. I add fictional customer Alex, invoice EXAMPLE-01 and a polite tone. Now I can explain those choices.'),
                ('EXAMPLE', 'Weak: Write a reminder. Improved: Write a polite reminder to fictional customer Alex about invoice EXAMPLE-01, requesting a reply.'),
            ] if teaching else [('WORKSHEET', 'Task: write a business reminder. Fictional customer: Alex; invoice: EXAMPLE-01. Choose a polite tone. Write your prompt here: ____. Explain your audience choice: ____. Explain your tone choice: ____. Check task, audience and tone against the supplied clarity criterion.')]
            for kind, content in assets:
                key = unit.key + ':' + kind.lower()
                item['material_keys'].append(key)
                materials.append({'key': key, 'kind': kind, 'title': 'Synthetic ' + kind,
                                  'content': content, 'citations': [citation]})
        units.append({'key': unit.key, 'items': [item]})
    values = {'input_digest': data.digest, 'units': units,
              'gaps': ['Synthetic model output; all original source diagnostics and gaps remain unresolved.']}
    output_type = {'ASSESSMENT': AssessmentDraft, 'TEACHER_CONTENT': TeacherDraft, 'TRAINER_CONTENT': TrainerDraft}[data.role]
    if materials:
        values['materials'] = materials
    return output_type(**values)


def whole(data):
    """The request input a block was cut from (S09d): the same input without its block."""
    return GenerationInput.model_validate({k: v for k, v in data.model_dump(mode='json').items() if k != 'block'})


# The review agent's synthetic refusal of a generated draft: model text, never an error message.
GENERATION_REJECTION = GenerationVerdict(verdict='REJECT', source_alignment=True, citation_support=True,
    intent_correct=True, content_complete=False,
    reason='Synthetic refusal: the worksheet names a criterion it does not supply.')


class SyntheticModels:
    """Synthetic generators and review agent: ``verdicts`` are returned in order, then ``verdict``.

    A review prompt holding :data:`REJECT_ONCE` (in a command requirement) is refused the first time it is seen,
    so the synthetic worker and the browser tests can show a refused draft followed by an accepted one. Only the
    review of a block is refused: the review of the assembled draft judges blocks already accepted (S09d).
    """

    def __init__(self, *verdicts):
        self.calls = []
        self.prompts = []
        self.reviews = []
        self.verdicts = list(verdicts)
        self.agent_configs = []
        self.inputs = []
        self.callback = None
        self.transform = None
        self.verdict = GenerationVerdict(verdict='ACCEPT', source_alignment=True,
            citation_support=True, intent_correct=True, content_complete=True,
            reason='Synthetic separate Lead review; not a real pedagogical validation.')
        self.llms = Mock(return_value='synthetic-client')

    def factory(self):
        catalog = load_model_catalog(ROOT / 'model.properties')
        skills = {'evidence-search': object()}
        registry = AgentRegistry.load(ROOT / 'agents/authoring', profiles=catalog.profiles,
            tools={'search_documents': object()}, skills=skills, settings=catalog.settings,
            categories=load_category_catalog(ROOT / 'categories'))
        dispatcher = AuthoringDispatcher(registry=registry, llm_factory=self.llms, skills=skills,
            contracts=CONTRACTS, context_budget=None, agent_factory=self.agent)
        return dispatcher, SimpleNamespace(kickoff=self.review), None

    def agent(self, **kwargs):
        self.agent_configs.append(kwargs)
        name = kwargs['role']
        def kickoff(prompt, response_format=None):
            payload = json.loads(prompt.split('\nDATA\n')[1])
            data = GenerationInput.model_validate(payload['input'])
            self.calls.append(name)
            self.prompts.append(prompt)
            self.inputs.append(data)
            if self.callback:
                self.callback(data)
            result = synthetic_draft(data)
            if self.transform:
                result = self.transform(data, result)
            if response_format is None:  # Prompt-schema contracts return text.
                return SimpleNamespace(raw=result.model_dump_json())
            return SimpleNamespace(pydantic=result)
        return SimpleNamespace(kickoff=kickoff)

    def review(self, prompt, response_format):
        assert response_format is GenerationVerdict
        self.calls.append('LEAD_REVIEW')
        self.reviews.append(prompt)
        if REJECT_ONCE in prompt and 'PROJECT_AUTHORING_BLOCK_REVIEW' in prompt and self.reviews.count(prompt) == 1:
            return SimpleNamespace(pydantic=GENERATION_REJECTION)
        return SimpleNamespace(pydantic=self.verdicts.pop(0) if self.verdicts else self.verdict)
