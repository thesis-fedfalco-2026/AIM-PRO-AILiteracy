import unittest
from unittest.mock import Mock, patch

from crewai import Task

from agent_system.flow_task import DelegatedTask
from agent_system.orchestrator import OrchestrationFlow
from learning.outputs import WorkerOutput
from learning.planning import LearningPlanDraft
from tests import test_orchestration as fixtures


class DelegatedTaskTest(unittest.TestCase):
    def make_task(self, delegate, guardrail):
        return DelegatedTask(name="step", description="Authorized brief",
            expected_output="EXPLANATION", output_pydantic=WorkerOutput,
            guardrail=guardrail, guardrail_max_retries=0, delegate=delegate)

    def test_typed_output_is_checked_before_publication(self):
        result = WorkerOutput(kind="EXPLANATION", content="Checked")
        delegate = Mock(return_value=result)
        checked = []

        def guardrail(output):
            checked.append(output.pydantic)
            return True, output

        task = self.make_task(delegate, guardrail)
        self.assertIsInstance(task, Task)
        output = task.execute_sync()
        self.assertIs(output.pydantic, result)
        self.assertIs(task.output, output)
        self.assertEqual(checked, [result])
        delegate.assert_called_once_with()

    def test_rejected_output_is_not_published_or_retried(self):
        delegate = Mock(return_value=WorkerOutput(kind="EXPLANATION", content="Untrusted"))
        checked = []

        def guardrail(output):
            checked.append(output)
            return False, "Rejected"

        task = self.make_task(delegate, guardrail)
        with self.assertRaisesRegex(ValueError, "rejected by guardrail"):
            task.execute_sync()
        self.assertIsNone(task.output)
        self.assertEqual(len(checked), 1)
        delegate.assert_called_once_with()

    def test_wrong_contract_never_reaches_semantic_guardrail(self):
        checked = []

        def guardrail(output):
            checked.append(output)
            return True, output

        task = self.make_task(lambda: {"content": "Untyped"}, guardrail)
        with self.assertRaisesRegex(ValueError, "structured contract"):
            task.execute_sync()
        self.assertIsNone(task.output)
        self.assertEqual(checked, [])


class OrchestrationFlowTest(unittest.TestCase):
    def build(self, **kwargs):
        helper = fixtures.OrchestrationExecutionTest()
        orchestrator, context = helper.build(**kwargs)
        return helper, orchestrator, context

    def test_flow_dispatches_each_step_and_keeps_only_scheduling_state(self):
        helper, orchestrator, context = self.build()
        with patch("crewai.flow.runtime.Memory", side_effect=AssertionError("No Flow memory")):
            flow = OrchestrationFlow(orchestrator, context.request, context)
            flow.kickoff()
        self.assertEqual(flow.response.kind, "ANSWER")
        self.assertEqual(flow.state.cursor, 3)
        self.assertEqual(set(flow.state.model_dump()), {"id", "cursor"})
        self.assertIsNone(flow.memory)
        self.assertIsNone(flow.persistence)
        self.assertEqual(helper.events, ['search', 'one', 'dependent', 'independent', 'synthesis'])

    def test_sequential_requests_get_fresh_flow_state(self):
        helper, orchestrator, context = self.build()
        first = orchestrator.run(context.request, context=context)
        records = orchestrator.last_records
        events = list(helper.events)
        second = orchestrator.run(context.request, context=context)
        self.assertEqual(first, second)
        self.assertEqual(orchestrator.last_records, records)
        self.assertEqual(helper.events, events + events)

    def test_empty_plan_finishes_without_dispatch_or_synthesis(self):
        helper, orchestrator, context = self.build(plan_override=LearningPlanDraft())
        from dataclasses import replace
        context = replace(context, request=context.request.model_copy(update={"intent": "CLARIFICATION"}))
        self.assertEqual(orchestrator.run(context.request, context=context).kind, "CLARIFICATION")
        self.assertEqual(helper.events, [])
        self.assertEqual([record.type for record in orchestrator.last_records], ["TaskPlan"])
