"""Real SDK/exporter integration without Langfuse or model network calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_system import telemetry


class DisabledTelemetryTest(unittest.TestCase):
    def test_disabled_does_not_import_sdk(self):
        script = '''import sys
from agent_system import telemetry
telemetry.initialize({})
with telemetry.observation("test") as span:
    span.update(output="text")
telemetry.flush()
assert not any(k == "langfuse" or k.startswith("openinference") for k in sys.modules)
'''
        subprocess.run([sys.executable, '-c', script], check=True)

    def test_mask_structured_and_embedded_identities(self):
        with patch.dict(telemetry._subjects, {'person@example.org': 'hashed-user'}):
            masked = telemetry.mask({'subject_key': 'person@example.org',
                                     'prompt': 'Question from person@example.org',
                                     'nested': [{'subjectKey': 'other'}]})
        self.assertNotIn('person@example.org', json.dumps(masked))
        self.assertEqual(masked['nested'][0]['subjectKey'], '[REDACTED]')

    def test_vendor_cloud_collection_is_disabled_in_project_storage(self):
        from tempfile import TemporaryDirectory
        from crewai.events.listeners.tracing.utils import should_enable_tracing, should_auto_collect_first_time_traces
        with TemporaryDirectory() as directory, patch.dict(os.environ):
            telemetry.configure_vendor_privacy(Path(directory))
            self.assertEqual(os.environ["CREWAI_DISABLE_TELEMETRY"], "true")
            self.assertEqual(Path(os.environ["CREWAI_STORAGE_DIR"]), Path(directory).resolve() / ".cache" / "crewai")
            self.assertFalse(should_enable_tracing())
            self.assertFalse(should_auto_collect_first_time_traces())

    def test_cloud_requires_synthetic_opt_in(self):
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            telemetry.initialize({'LANGFUSE_ENABLED': 'true', 'LANGFUSE_BASE_URL': 'https://cloud.langfuse.com'})


class TelemetryIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
            import langfuse
        except ImportError:
            raise unittest.SkipTest('Install observability dependencies to exercise the real SDK')
        cls.exporter = InMemorySpanExporter()
        telemetry.initialize({'LANGFUSE_ENABLED': 'true', 'LANGFUSE_BASE_URL': 'http://127.0.0.1:3000',
                              'LANGFUSE_PUBLIC_KEY': 'pk-test', 'LANGFUSE_SECRET_KEY': 'sk-test',
                              'LANGFUSE_HASH_SALT': 'test-private-salt'}, span_exporter=cls.exporter)
        cls.client = telemetry._client

    @classmethod
    def tearDownClass(cls):
        from openinference.instrumentation.crewai import CrewAIInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor
        CrewAIInstrumentor().uninstrument()
        OpenAIInstrumentor().uninstrument()
        cls.client.shutdown()
        telemetry._client = None
        telemetry._subjects.clear()

    def setUp(self):
        self.exporter.clear()
        # Scores are HTTP API events, separate from the in-memory OTel exporter.
        self.scores = patch.object(self.client, 'create_score').start()
        self.addCleanup(patch.stopall)

    def run_request(self, *, reject=False, invalid=False, private=False):
        from dataclasses import replace
        from tests.test_learning_outputs import OutputsTest
        from tests.test_learning_planning import draft_step
        builder = OutputsTest()
        orch, context = builder.build((draft_step(depends_on=('one',)),) if invalid else (draft_step(),), reject=reject)
        if not private:
            root = context.snapshot.context.model_copy(update={'fields': {
                **context.snapshot.context.fields, 'mode': 'PREPARATION'}})
            context = replace(context, snapshot=replace(context.snapshot, context=root))
        result = orch.run(context.request, context=context)
        telemetry.flush()
        return result, self.exporter.get_finished_spans(), context

    def test_request_span_tree_and_scores(self):
        result, spans, context = self.run_request()
        self.assertEqual(result.kind, 'ANSWER')
        root, = [s for s in spans if s.name == 'learning.request']
        step, = [s for s in spans if s.name == 'step.one']
        self.assertIsNone(root.parent)
        self.assertEqual(step.parent.span_id, root.context.span_id)
        self.assertEqual({s.context.trace_id for s in spans}, {root.context.trace_id})
        self.assertIn('check_worker_output', [s.name for s in spans])
        self.assertIn('check_final_response', [s.name for s in spans])
        # One step: its worker review only; a single accepted step is not re-synthesized.
        self.assertEqual(len([s for s in spans if s.name == 'semantic_review']), 1)
        self.assertGreaterEqual(self.scores.call_count, 5)
        self.assertNotIn(context.request.subject_key, json.dumps([dict(s.attributes) for s in spans]))

    def test_plan_rejection_has_cause(self):
        result, spans, _ = self.run_request(invalid=True)
        self.assertEqual(result.kind, 'FAILURE')
        # A plan-rule violation gets one corrected attempt; both are inspectable.
        gates = [s for s in spans if s.name == 'authorize_plan']
        self.assertEqual(len(gates), 2)
        for gate in gates:
            self.assertEqual(gate.attributes['langfuse.observation.level'], 'ERROR')
            self.assertTrue(gate.attributes['langfuse.observation.status_message'])
        self.assertFalse(any(s.name.startswith('step.') for s in spans))

    def test_rejected_worker_review_remains_inspectable(self):
        result, spans, _ = self.run_request(reject=True)
        self.assertEqual(result.kind, 'FAILURE')
        review, = [s for s in spans if s.name == 'semantic_review']
        self.assertIn('REJECT', review.attributes['langfuse.observation.output'])
        self.assertIn('Checked', review.attributes['langfuse.observation.output'])

    def test_mcp_retrieval_is_nested_under_step(self):
        from tempfile import TemporaryDirectory
        from agent_system.mcp_runtime import DocumentSearchClient, build_document_search_params
        from learning.context import LearningRequest
        from learning.contracts import EntityRef
        from learning.store import LearningStore
        from main import BASE_DIR
        from smoke import prepare_demo
        from tests.learning_runtime import demo_orchestrator
        search = DocumentSearchClient(build_document_search_params(BASE_DIR, {"SEARCH_BACKEND": "mock"}))
        orch = demo_orchestrator(search.search)
        with TemporaryDirectory() as directory, LearningStore(Path(directory) / "state.sqlite") as store:
            service = prepare_demo(store, lambda: orch)
            request = LearningRequest(request_id="trace-mcp", context_ref=store.read_context("demo").ref,
                subject_key="learner", text="Synthetic deployment", topic_refs=(
                    EntityRef(type="Topic", id="deployment", version="1"),))
            with patch.object(telemetry, "_synthetic", True):
                response = service.request(request)
        telemetry.flush()
        self.assertEqual(response.kind, "ANSWER")
        spans = self.exporter.get_finished_spans()
        retrieval, = [s for s in spans if s.name == "document_search"]
        step, = [s for s in spans if s.name == "step.teach"]
        self.assertEqual(retrieval.parent.span_id, step.context.span_id)
        self.assertIn('resource_key', retrieval.attributes['langfuse.observation.output'])
        self.assertIn('technical-deployment-guide', retrieval.attributes['langfuse.observation.output'])

    def test_automatic_error_events_are_masked(self):
        from opentelemetry import trace
        token = telemetry._learning.set(True)
        try:
            with telemetry.observation("error-test"):
                trace.get_current_span().add_event("exception", {"exception.message": "PRIVATE_SUBMISSION"})
        finally:
            telemetry._learning.reset(token)
        telemetry.flush()
        span, = self.exporter.get_finished_spans()
        self.assertNotIn("PRIVATE_SUBMISSION", str(span.events[0].attributes))

    def test_native_openrouter_stream_captures_prompt_completion_and_tokens(self):
        import httpx
        from agent_system.openrouter import OpenRouterCompletion
        from crewai.events.utils.console_formatter import set_suppress_console_output
        set_suppress_console_output(True)
        chunks = [
            {"id": "test", "object": "chat.completion.chunk", "created": 1, "model": "test:free",
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Synthetic answer"}, "finish_reason": None}]},
            {"id": "test", "object": "chat.completion.chunk", "created": 1, "model": "test:free",
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}},
        ]
        def respond(request):
            self.assertTrue(json.loads(request.content)["stream_options"]["include_usage"])
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                text="".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n")
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            llm = OpenRouterCompletion(model="test:free", api_key="synthetic", base_url="https://openrouter.ai/api/v1",
                stream=True)
            from openai import OpenAI
            llm._client = OpenAI(api_key="synthetic", http_client=http)
            with telemetry.observation("native-test"):
                result = llm.call("Synthetic question")
        telemetry.flush()
        self.assertIn("Synthetic answer", result)
        spans = self.exporter.get_finished_spans()
        sdk, = [s for s in spans if s.instrumentation_scope.name == "openinference.instrumentation.openai"]
        attrs = dict(sdk.attributes)
        self.assertIn("Synthetic question", json.dumps(attrs))
        self.assertIn("Synthetic answer", json.dumps(attrs))
        self.assertEqual(attrs["llm.token_count.prompt"], 12)
        self.assertEqual(attrs["llm.token_count.completion"], 3)
        self.assertGreater(sdk.end_time, sdk.start_time)

    def test_learning_content_is_masked_at_export(self):
        _, spans, _ = self.run_request(private=True)
        serialized = json.dumps([dict(s.attributes) for s in spans])
        self.assertNotIn('BAD_OUTPUT', serialized)
        self.assertIn('[REDACTED: LEARNING]', serialized)


if __name__ == '__main__':
    unittest.main()
