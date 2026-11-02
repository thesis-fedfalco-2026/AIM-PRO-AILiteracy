from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from agent_system.authoring import AuthoringDispatcher
from agent_system.config import ConfigurationError, load_category_catalog, load_model_catalog
from agent_system.registry import AgentRegistry
from aimpro.syllabus import SyllabusDraft
from learning.outputs import WorkerOutput
from tests.syllabus_fixtures import syllabus


ROOT = Path(__file__).resolve().parents[1]


class AuthoringDispatchTest(unittest.TestCase):
    def setUp(self):
        catalog = load_model_catalog(ROOT / 'model.properties')
        self.skills = {'evidence-search': object()}
        self.registry = AgentRegistry.load(ROOT / 'agents' / 'authoring',
            profiles=catalog.profiles, tools={'search_documents': object()}, skills=self.skills,
            settings=catalog.settings, categories=load_category_catalog(ROOT / 'categories'),
            excluded_names={catalog.lead.name})
        self.clients = Mock(return_value='configured-client')
        self.calls = []
        self.result = syllabus()
        self.outputs = []

    def factory(self, **kwargs):
        self.calls.append(kwargs)
        def kickoff(prompt, response_format):
            self.outputs.append((prompt, response_format))
            return SimpleNamespace(pydantic=self.result)
        return SimpleNamespace(kickoff=kickoff)

    def dispatcher(self, registry=None):
        return AuthoringDispatcher(registry=registry or self.registry,
            llm_factory=self.clients, skills=self.skills,
            contracts={'syllabus-designer': ('curator', SyllabusDraft)},
            context_budget=100, agent_factory=self.factory)

    def test_named_curator_uses_typed_contract_category_settings_and_no_direct_tools(self):
        dispatcher = self.dispatcher()
        result = dispatcher.run('syllabus-designer', 'Explicit assigned authoring data')
        self.assertEqual(result, self.result)
        self.assertIsNot(result, self.result)
        call = self.calls[0]
        self.assertEqual(call['role'], 'syllabus-designer')
        self.assertIn('CATEGORY curator', call['backstory'])
        self.assertEqual(call['tools'], [])
        self.assertEqual(call['skills'], [self.skills['evidence-search']])
        self.assertFalse(call['allow_delegation'])
        self.assertEqual(self.clients.call_args.args[0], 'openrouter')
        self.assertEqual(self.clients.call_args.args[1].temperature, .2)
        self.assertIs(self.outputs[0][1], SyllabusDraft)

    def test_unknown_dispatch_and_wrong_structured_outputs_are_rejected(self):
        dispatcher = self.dispatcher()
        with self.assertRaises(ConfigurationError):
            dispatcher.run('resource-candidate-researcher', 'Unregistered task')
        self.assertEqual(self.calls, [])
        self.result = WorkerOutput(kind='CHANGE_PROPOSAL', content='Untyped outline')
        with self.assertRaisesRegex(ValueError, 'structured authoring output'):
            dispatcher.run('syllabus-designer', 'Task')

    def test_local_worker_budget_is_independent_of_lead_profile(self):
        config = self.registry.get('syllabus-designer').model_copy(update={'profile': 'local'})
        dispatcher = self.dispatcher(AgentRegistry([config]))
        with self.assertRaisesRegex(ValueError, 'budget'):
            dispatcher.run('syllabus-designer', 'X' * 101)
        self.assertEqual(self.calls, [])
        self.dispatcher().run('syllabus-designer', 'X' * 101)
        self.assertEqual(len(self.calls), 1)

    def test_bad_category_mode_output_or_capabilities_fail_before_client_creation(self):
        config = self.registry.get('syllabus-designer')
        for fields in ({'category': 'evaluator'}, {'mode': 'LEARNING'},
                       {'expected_output': 'SUPPORT_MATERIAL'}, {'tools': ('write_database',)},
                       {'skills': ('missing',)}):
            with self.subTest(fields=fields), self.assertRaises(ConfigurationError):
                self.dispatcher(AgentRegistry([config.model_copy(update=fields)]))
        self.clients.assert_not_called()
        self.assertEqual(self.calls, [])
