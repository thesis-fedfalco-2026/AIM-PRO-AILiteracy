from contextlib import redirect_stdout
from io import StringIO
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_system.config import ConfigurationError, load_model_catalog
from aimpro.lead import AuthoringReview, main as lead_main, prepare_input
import main


class AimproRuntimeTest(unittest.TestCase):
    def test_authoring_builder_creates_distinct_registry_curator_and_review_lead(self):
        from aimpro.syllabus import SyllabusDraft
        from tests.syllabus_fixtures import syllabus
        catalog = load_model_catalog(main.BASE_DIR / 'model.properties')
        calls = []
        def factory(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(kickoff=lambda prompt, response_format: SimpleNamespace(pydantic=syllabus()))
        with patch.object(main, 'DocumentSearchClient', side_effect=AssertionError('MCP is service mediated')):
            dispatcher, lead, budget = main.build_aimpro_authoring(model_catalog=catalog,
                environ={'OPENROUTER_API_KEY': 'test'}, client_factory=lambda **kwargs: kwargs,
                agent_factory=factory)
        self.assertEqual([c['role'] for c in calls], ['lead'])
        self.assertEqual([s.name for s in dispatcher.registry.summaries()],
                         ['assessment-designer', 'practice-designer', 'syllabus-designer',
                          'teaching-designer-structured', 'teaching-designer'])
        result = dispatcher.run('syllabus-designer', 'Assigned source and evidence')
        self.assertIs(type(result), SyllabusDraft)
        self.assertEqual([c['role'] for c in calls], ['lead', 'syllabus-designer'])
        self.assertIsNot(calls[0]['llm'], calls[1]['llm'])
        self.assertTrue(all(c['tools'] == [] and not c['allow_delegation'] for c in calls))
        self.assertIn('CATEGORY curator', calls[1]['backstory'])
        self.assertIsNone(budget)

    def test_builder_uses_configured_lead_without_search_or_workers(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        calls = []
        def agent_factory(**kwargs):
            calls.append(kwargs)
            return "lead"
        with patch.object(main, "DocumentSearchClient", side_effect=AssertionError("Unexpected retrieval")), \
             patch.object(main.AgentRegistry, "load", side_effect=AssertionError("Unexpected workers")):
            lead, budget = main.build_aimpro_lead(model_catalog=catalog,
                environ={"OPENROUTER_API_KEY": "test"},
                client_factory=lambda **kwargs: kwargs, agent_factory=agent_factory)
        self.assertEqual(lead, "lead")
        self.assertIsNone(budget)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tools"], [])
        self.assertFalse(calls[0]["allow_delegation"])
        self.assertEqual(calls[0]["llm"]["model"], catalog.profiles[catalog.lead.profile].model)

    def test_local_budget_is_preserved(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        catalog = catalog.model_copy(update={"lead": catalog.lead.model_copy(update={"profile": "local"})})
        _, budget = main.build_aimpro_lead(model_catalog=catalog, environ={"VLLM_API_KEY": "test"},
            client_factory=lambda **kw: kw, agent_factory=lambda **kw: kw)
        self.assertEqual(budget, catalog.orchestrator.max_context_chars)

    def test_builder_rejects_review_tools_and_missing_credentials(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        with self.assertRaises(ConfigurationError):
            main.build_aimpro_lead(model_catalog=catalog, environ={})
        catalog = catalog.model_copy(update={"lead": catalog.lead.model_copy(update={"tools": ("search_documents",)})})
        with self.assertRaises(ConfigurationError):
            main.build_aimpro_lead(model_catalog=catalog, environ={})

    def test_run_cli_reaches_lead_and_keeps_findings(self):
        data = prepare_input()
        calls = []
        def kickoff(prompt, response_format):
            calls.append(response_format)
            return SimpleNamespace(pydantic=AuthoringReview(
                source_sha256=data.source.source_sha256,
                metamodel_fingerprint=data.metamodel_fingerprint, summary="Review only."))
        output = StringIO()
        with patch.object(main, "build_aimpro_lead", return_value=(SimpleNamespace(kickoff=kickoff), None)), redirect_stdout(output):
            lead_main(["--run"])
        response = json.loads(output.getvalue())
        self.assertEqual(calls, [AuthoringReview])
        self.assertFalse(response["conforms_to_generated_contracts"])
        self.assertEqual(len(response["contract_findings"]), 5)
