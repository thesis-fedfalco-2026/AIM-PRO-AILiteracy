import unittest
import logging
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from agent_system.config import AgentConfig, OrchestratorSettings
from agent_system.orchestrator import Orchestrator, OrchestrationError
from agent_system.plan import ExecutionPlan, PlanStep, RetrievalRequest, validate_and_order_plan
from agent_system.registry import AgentRegistry
from agent_system.task_tool import TaskTool


class PlanValidationTest(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry([
            AgentConfig(
                name="researcher",
                description="Searches documents.",
                model="local",
                tools=("search_documents",),
                system_prompt="Research.",
                source=Path("researcher.md"),
            ),
            AgentConfig(
                name="writer",
                description="Writes answers.",
                model="local",
                system_prompt="Write.",
                source=Path("writer.md"),
            ),
        ])
        self.settings = OrchestratorSettings(
            max_steps=6,
            max_input_chars=8000,
            max_task_chars=2000,
            max_context_chars=8000,
        )

    def test_valid_plan_is_returned_in_stable_dependency_order(self):
        plan = ExecutionPlan(steps=(
            PlanStep(id="final", agent="writer", task="Synthesize.", depends_on=("facts",)),
            PlanStep(id="outline", agent="writer", task="Outline."),
            PlanStep(
                id="facts",
                agent="researcher",
                task="Find facts.",
                retrieval=RetrievalRequest(tool="search_documents", query="topic", k=3),
            ),
        ))

        ordered = validate_and_order_plan(plan, self.registry, self.settings)

        self.assertEqual(tuple(step.id for step in ordered), ("outline", "facts", "final"))

    def test_plan_rejects_duplicate_ids_unknown_agents_and_unknown_dependencies(self):
        cases = {
            "duplicate ids": (
                PlanStep(id="same", agent="writer", task="First."),
                PlanStep(id="same", agent="writer", task="Second."),
            ),
            "unknown agent": (PlanStep(id="one", agent="missing", task="Task."),),
            "unknown dependency": (
                PlanStep(id="one", agent="writer", task="Task.", depends_on=("missing",)),
            ),
            "self dependency": (
                PlanStep(id="one", agent="writer", task="Task.", depends_on=("one",)),
            ),
        }
        for label, steps in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_and_order_plan(ExecutionPlan(steps=steps), self.registry, self.settings)

    def test_plan_rejects_cycles_and_too_many_steps(self):
        cycle = ExecutionPlan(steps=(
            PlanStep(id="one", agent="writer", task="One.", depends_on=("two",)),
            PlanStep(id="two", agent="writer", task="Two.", depends_on=("one",)),
        ))
        with self.assertRaises(ValueError):
            validate_and_order_plan(cycle, self.registry, self.settings)

        too_many = ExecutionPlan(steps=(
            PlanStep(id="one", agent="writer", task="One."),
            PlanStep(id="two", agent="writer", task="Two."),
        ))
        with self.assertRaises(ValueError):
            validate_and_order_plan(
                too_many,
                self.registry,
                self.settings.model_copy(update={"max_steps": 1}),
            )

    def test_plan_rejects_unauthorized_retrieval_and_out_of_range_k(self):
        retrieval = RetrievalRequest(tool="search_documents", query="topic", k=3)
        plan = ExecutionPlan(steps=(
            PlanStep(id="one", agent="writer", task="Search.", retrieval=retrieval),
        ))
        with self.assertRaises(ValueError):
            validate_and_order_plan(plan, self.registry, self.settings)

        for k in (0, 21):
            with self.subTest(k=k), self.assertRaises(ValueError):
                RetrievalRequest(tool="search_documents", query="topic", k=k)

    def test_plan_models_forbid_extras_are_frozen_and_use_literal_tool(self):
        for model in (RetrievalRequest, PlanStep, ExecutionPlan):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.model_config["extra"], "forbid")
                self.assertTrue(model.model_config["frozen"])

        with self.assertRaises(ValidationError):
            RetrievalRequest(tool="other", query="topic", k=3)
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate({"steps": [], "extra": True})

        step = PlanStep(id="one", agent="writer", task="Write.")
        with self.assertRaises(ValidationError):
            step.task = "Changed."

    def test_plan_rejects_oversized_task_and_query(self):
        settings = self.settings.model_copy(
            update={"max_task_chars": 4, "max_input_chars": 4}
        )
        cases = (
            PlanStep(id="one", agent="writer", task="SENTINEL_TASK"),
            PlanStep(
                id="one",
                agent="researcher",
                task="Task",
                retrieval=RetrievalRequest(
                    tool="search_documents", query="SENTINEL_QUERY", k=3
                ),
            ),
        )
        for step in cases:
            with self.subTest(step=step.id), self.assertRaises(ValueError) as raised:
                validate_and_order_plan(
                    ExecutionPlan(steps=(step,)), self.registry, settings
                )
            self.assertNotIn("SENTINEL", str(raised.exception))

    def test_empty_plan_is_valid(self):
        self.assertEqual(
            validate_and_order_plan(ExecutionPlan(), self.registry, self.settings),
            (),
        )


class OrchestrationExecutionTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.worker_prompts = {}
        self.synthesis = []
        self.settings = OrchestratorSettings(
            max_steps=6, max_input_chars=8000, max_task_chars=2000,
            max_context_chars=1000,
        )
        self.registry = AgentRegistry([
            AgentConfig(
                name=name, description="Specialist", model="local",
                tools=("search_documents",) if name == "agent-v" else (),
                system_prompt="PRIVATE", source=Path(f"{name}.md"),
            )
            for name in ("agent-v", "agent-x")
        ])

    def build(self, plan, *, search_error=False, worker_error=False,
              synthesis_error=False, long_context=False, plan_output=None):
        test = self

        class Lead:
            def kickoff(self, prompt, response_format=None):
                if response_format is not None:
                    test.assertIs(response_format, ExecutionPlan)
                    return plan_output if plan_output is not None else SimpleNamespace(pydantic=plan)
                test.events.append(("synthesize",))
                test.synthesis.append(prompt)
                if synthesis_error:
                    raise RuntimeError("synthesis unavailable")
                return SimpleNamespace(raw="final answer")

        def search(query, k):
            self.events.append(("search", query, k))
            if search_error:
                raise RuntimeError("SECRET retrieval details")
            return {"backend": "mock", "query": query, "k": k, "hits": [{
                "id": "doc", "title": "Evidence", "text": "retrieved document "
                + ("x" * 5000 if long_context else "facts"), "score": 1.0,
                "source": "fixture", "metadata": {},
            }]}

        def worker(config, task):
            self.events.append(("worker", config.name))
            self.worker_prompts[config.name] = task
            if worker_error and config.name == "agent-v":
                raise RuntimeError("SECRET worker details")
            return "research result " + ("y" * 5000 if long_context else "facts")

        logger = logging.getLogger("test.orchestration")
        return Orchestrator(
            lead_llm="lead", registry=self.registry,
            task_tool=TaskTool(registry=self.registry, worker=worker, logger=logger),
            search=search, settings=self.settings, logger=logger,
            agent_factory=lambda **kwargs: Lead(),
        )

    def plan(self, *, independent=False, retrieval=True):
        steps = [
            PlanStep(id="review", agent="agent-x", task="Review research.",
                     depends_on=("research",)),
            PlanStep(id="research", agent="agent-v", task="Find evidence.",
                     retrieval=RetrievalRequest(tool="search_documents",
                                                query="technical query", k=3)
                     if retrieval else None),
        ]
        if independent:
            steps.append(PlanStep(id="independent", agent="agent-x", task="Separate analysis."))
        return ExecutionPlan(steps=tuple(steps))

    def test_executes_dependencies_in_order_and_bounds_untrusted_context(self):
        orchestrator = self.build(self.plan(), long_context=True)

        self.assertEqual(orchestrator.answer("Question"), "final answer")

        self.assertEqual(self.events, [
            ("search", "technical query", 3), ("worker", "agent-v"),
            ("worker", "agent-x"), ("synthesize",),
        ])
        self.assertIn("retrieved document", self.worker_prompts["agent-v"])
        self.assertIn("research result", self.worker_prompts["agent-x"])
        for prompt in self.worker_prompts.values():
            self.assertLessEqual(len(prompt), 1000)
            self.assertIn("untrusted", prompt.lower())
            self.assertTrue(prompt.endswith("\n[context truncated]"))
        self.assertLessEqual(len(self.synthesis[0]), 1000)
        self.assertIn("untrusted", self.synthesis[0].lower())
        self.assertIn("[context truncated]", self.synthesis[0])
        self.assertTrue(self.synthesis[0].endswith("\nQuestion:\nQuestion"))

    def test_entire_plan_is_validated_before_search_or_worker(self):
        cases = (
            PlanStep(id="bad", agent="agent-x", task="Unauthorized search.",
                     retrieval=RetrievalRequest(tool="search_documents", query="q", k=3)),
            PlanStep(id="bad", agent="missing", task="Unknown worker."),
            PlanStep(id="bad", agent="agent-x", task="Unknown dependency.",
                     depends_on=("missing",)),
        )
        for step in cases:
            with self.subTest(step=step.task):
                plan = ExecutionPlan(steps=(
                    PlanStep(id="valid", agent="agent-v", task="Run first."), step,
                ))
                with self.assertRaises(ValueError):
                    self.build(plan).answer("Question")
                self.assertEqual(self.events, [])

    def test_rejects_missing_wrong_and_free_form_plans(self):
        class DerivedPlan(ExecutionPlan):
            pass

        for output in (
            SimpleNamespace(raw='{"steps": []}'),
            SimpleNamespace(pydantic={"steps": []}),
            SimpleNamespace(pydantic=DerivedPlan()),
        ):
            with self.subTest(output=output):
                with self.assertRaisesRegex(OrchestrationError, "^Lead returned an invalid execution plan$"):
                    self.build(ExecutionPlan(), plan_output=output).answer("Question")
                self.assertEqual(self.events, [])

    def test_retrieval_failure_skips_worker_and_dependents_but_runs_independent(self):
        orchestrator = self.build(self.plan(independent=True), search_error=True)
        with self.assertLogs("test.orchestration", level="ERROR") as captured:
            self.assertEqual(orchestrator.answer("Question"), "final answer")

        self.assertEqual(self.events, [
            ("search", "technical query", 3), ("worker", "agent-x"), ("synthesize",),
        ])
        self.assert_safe_partial_failure("retrieval_failed", captured.output)

    def test_worker_failure_skips_dependents_but_runs_independent(self):
        orchestrator = self.build(self.plan(independent=True, retrieval=False), worker_error=True)
        with self.assertLogs("test.orchestration", level="ERROR") as captured:
            self.assertEqual(orchestrator.answer("Question"), "final answer")

        self.assertEqual(self.events, [
            ("worker", "agent-v"), ("worker", "agent-x"), ("synthesize",),
        ])
        self.assert_safe_partial_failure("worker_failed", captured.output)

    def assert_safe_partial_failure(self, label, logs):
        context = self.synthesis[0]
        for expected in ("research: failed", "review: skipped", "independent: success",
                         label, "dependency_failed", "research result"):
            self.assertIn(expected, context)
        self.assertNotIn("SECRET", context)
        self.assertNotIn("SECRET", " ".join(logs))

    def test_all_failures_raise_without_synthesis(self):
        for retrieval in (True, False):
            with self.subTest(retrieval=retrieval):
                self.events.clear()
                orchestrator = self.build(self.plan(retrieval=retrieval),
                                          search_error=retrieval, worker_error=not retrieval)
                with self.assertLogs("test.orchestration", level="ERROR"):
                    with self.assertRaisesRegex(OrchestrationError, "^All plan steps failed$"):
                        orchestrator.answer("Question")
                self.assertNotIn(("synthesize",), self.events)
                self.assertNotIn(("worker", "agent-x"), self.events)

    def test_synthesis_exception_propagates(self):
        with self.assertRaisesRegex(RuntimeError, "^synthesis unavailable$"):
            self.build(self.plan(), synthesis_error=True).answer("Question")
        self.assertEqual(self.events[-1], ("synthesize",))

    def test_tiny_context_limit_uses_truncated_marker(self):
        self.settings = self.settings.model_copy(update={"max_context_chars": 5})
        self.build(ExecutionPlan()).answer("Question")
        self.assertEqual(self.synthesis, ["\n[con"])

    def test_near_limit_question_preserves_execution_context(self):
        self.settings = self.settings.model_copy(update={
            "max_input_chars": 1000, "max_context_chars": 1000,
        })

        self.build(self.plan()).answer("q" * 1000)

        research = self.worker_prompts["agent-v"]
        review = self.worker_prompts["agent-x"]
        synthesis = self.synthesis[0]
        for prompt in (research, review, synthesis):
            self.assertLessEqual(len(prompt), 1000)
        self.assertIn("Find evidence.", research)
        self.assertIn("retrieved document facts", research)
        self.assertIn("Review research.", review)
        self.assertIn("research result facts", review)
        self.assertIn("research: success", synthesis)
        self.assertIn("review: success", synthesis)
        self.assertIn("research: research result facts", synthesis)
        self.assertIn("review: research result facts", synthesis)

    def test_synthesis_keeps_over_half_question_when_small_results_fit(self):
        self.settings = self.settings.model_copy(update={"max_context_chars": 1000})
        question = "q" * 600

        self.build(self.plan(retrieval=False)).answer(question)

        synthesis = self.synthesis[0]
        self.assertLessEqual(len(synthesis), 1000)
        self.assertIn(f"Question:\n{question}", synthesis)
        self.assertIn("research: research result facts", synthesis)
        self.assertIn("review: research result facts", synthesis)

    def test_large_synthesis_result_preserves_question_statuses_and_useful_result(self):
        self.settings = self.settings.model_copy(update={"max_context_chars": 400})

        self.build(self.plan(retrieval=False), long_context=True).answer("Original question")

        synthesis = self.synthesis[0]
        self.assertLessEqual(len(synthesis), 400)
        self.assertIn("Question:\nOriginal question", synthesis)
        self.assertIn("research: success", synthesis)
        self.assertIn("review: success", synthesis)
        self.assertIn("research: research result", synthesis)
        self.assertIn("[context truncated]", synthesis)


if __name__ == "__main__":
    unittest.main()
