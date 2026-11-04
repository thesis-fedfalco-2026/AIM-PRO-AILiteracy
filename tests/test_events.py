from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agent_system import events
from agent_system.events import Event, JsonlEventLog, MemoryEventLog, read_events
from agent_system.metrics import run_metrics, summarize
from document_search.backend import build_backend
from learning.context import LearningRequest
from learning.store import LearningStore
from smoke import prepare_demo
from tests.learning_fixtures import ref
from tests.learning_runtime import demo_orchestrator

QUESTION = "Explain deployment"


class EventLogTest(unittest.TestCase):
    def test_events_reject_content_and_unknown_types(self):
        base = dict(event_id="e", run_id="r", seq=0, time="t")
        Event(type="review", data={"stage": "FINAL", "verdict": "ACCEPT"}, **base)
        with self.assertRaisesRegex(ValueError, "looks like content"):
            Event(type="review", data={"nested": [{"reason": "x" * (events.MAX_TEXT + 1)}]}, **base)
        with self.assertRaises(ValueError):
            Event(type="prompt.text", **base)

    def test_emit_requires_a_bound_run_and_follows_copied_contexts(self):
        log = MemoryEventLog()
        events.emit("review", stage="FINAL", verdict="ACCEPT")
        with events.run(log, request_id="q", context_id="c", mode="LEARNING") as bound:
            events.emit("run.started", intent="EXPLAIN")
            with ThreadPoolExecutor(1) as pool:
                pool.submit(copy_context().run, events.emit, "worker.call", step_id="s").result()
        events.emit("run.finished")
        self.assertEqual([e.type for e in log.events], ["run.started", "worker.call"])
        self.assertEqual([e.seq for e in log.events], [0, 1])
        self.assertEqual({e.run_id for e in log.events}, {bound.run_id})
        self.assertEqual(log.events[1].mode, "LEARNING")

    def test_rejected_event_never_breaks_a_non_strict_run(self):
        log = MemoryEventLog(strict=False)
        with events.run(log), self.assertLogs("agent_system.events", "WARNING"):
            events.emit("review", reason="x" * 500)
        self.assertEqual(log.events, [])
        with events.run(MemoryEventLog()), self.assertRaises(ValueError):
            events.emit("review", reason="x" * 500)

    def test_jsonl_round_trip_is_owner_readable_only(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "logs" / "events.jsonl"
            with events.run(JsonlEventLog(path), request_id="q"):
                events.emit("run.started", intent="EXPLAIN")
                events.emit("run.finished", response_kind="ANSWER", duration_ms=5)
            restored = read_events(path)
            self.assertEqual([e.type for e in restored], ["run.started", "run.finished"])
            self.assertEqual(json.loads(path.read_text().splitlines()[0])["schema"], "alm.event/1")
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_provider_calls_are_attributed_to_the_run_with_tokens(self):
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.types.llm_events import (
            LLMCallCompletedEvent, LLMCallFailedEvent, LLMCallStartedEvent, LLMCallType)
        log = MemoryEventLog()
        with patch.object(events, "_provider_installed", False), crewai_event_bus.scoped_handlers():
            events.install_provider_listener()
            with events.run(log):
                for call_id, outcome in (("a", "ok"), ("b", "error")):
                    crewai_event_bus.emit(self, LLMCallStartedEvent(call_id=call_id, model="m"))
                    crewai_event_bus.emit(self, LLMCallCompletedEvent(
                        call_id=call_id, model="m", response="r", call_type=LLMCallType.LLM_CALL,
                        usage={"prompt_tokens": 7, "completion_tokens": 3}) if outcome == "ok"
                        else LLMCallFailedEvent(call_id=call_id, model="m", error="boom"))
                    events.flush_provider_events()
        calls = [e.data for e in log.events]
        self.assertEqual([c["status"] for c in calls], ["ok", "error"])
        self.assertEqual((calls[0]["input_tokens"], calls[0]["output_tokens"]), (7, 3))
        self.assertIsNotNone(calls[0]["duration_ms"])
        self.assertNotIn("boom", json.dumps(calls[1]))


class OrchestratorEventsTest(unittest.TestCase):
    def ask(self, **options):
        log = MemoryEventLog()
        with TemporaryDirectory() as directory, LearningStore(Path(directory) / "state.sqlite") as store:
            backend = build_backend({"SEARCH_BACKEND": "mock"})
            self.addCleanup(backend.close)
            orchestrator = demo_orchestrator(backend.search_documents, **options)
            orchestrator.events_log = log
            service = prepare_demo(store, lambda: orchestrator)
            response = service.request(LearningRequest(
                request_id="request", context_ref=store.read_context("demo").ref, subject_key="learner",
                text=QUESTION, topic_refs=(ref("Topic", "deployment"),)))
        return response, log.events

    def test_accepted_request_records_the_full_path_without_content(self):
        response, recorded = self.ask()
        self.assertEqual(response.kind, "ANSWER")
        self.assertEqual([e.type for e in recorded], [
            "run.started", "lead.call", "plan.decided", "retrieval", "worker.call", "lead.call",
            "review", "step.finished", "lead.call", "lead.call", "review", "final.checked", "run.finished"])
        self.assertEqual(len({e.run_id for e in recorded}), 1)
        serialized = json.dumps([e.model_dump(mode="json") for e in recorded])
        for text in (QUESTION, "approved release procedure", "learner"):
            self.assertNotIn(text, serialized)
        [run] = run_metrics(recorded)
        self.assertEqual(run["lead_calls"], {"LearningPlanDraft": 1, "SemanticReview": 2, "LearningResponse": 1})
        self.assertEqual(run["model_calls"], 5)
        self.assertEqual(run["plan_status"], "AUTHORIZED")
        self.assertEqual(run["reviews"], {"WORKER": {"ACCEPT": 1}, "FINAL": {"ACCEPT": 1}})
        self.assertEqual(run["final"]["response_kind"], "ANSWER")

    def test_rejected_worker_is_counted_and_has_no_synthesis(self):
        response, recorded = self.ask(reject_stage="WORKER")
        self.assertEqual(response.kind, "FAILURE")
        summary = summarize(recorded)
        self.assertEqual(summary["worker_steps"], {"executed": 1, "rejected": 1, "rejection_rate": 1.0})
        self.assertEqual(summary["reviews"]["WORKER"]["reject_rate"], 1.0)
        self.assertEqual(summary["finding_codes"], {"R18": 1})
        self.assertEqual(summary["lead_calls"], {"LearningPlanDraft": 1, "SemanticReview": 1})
        self.assertNotIn("final.checked", [e.type for e in recorded])
        self.assertEqual(summary["response_kinds"], {"FAILURE": 1})


if __name__ == "__main__":
    unittest.main()
