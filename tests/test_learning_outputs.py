from pathlib import Path
from agent_system.config import parse_agent_file
from dataclasses import replace
import json
import logging
from types import SimpleNamespace
import unittest

from agent_system.config import OrchestratorSettings
from agent_system.plan import PlanStep
from agent_system.orchestrator import Orchestrator
from agent_system.task_tool import TaskTool
from learning.outputs import WorkerOutput, LearningResponse, SemanticReview, ProposedChange, build_brief, check_worker_output, check_final_response, task_result
from learning.planning import LearningPlanDraft, LearningStepDraft, authorize_plan
from tests.test_learning_planning import draft_step, run_context
from tests.test_learning_profiles import specialization, registry


class OutputsTest(unittest.TestCase):
    def test_final_failure_is_not_promoted_when_tasks_are_partial(self):
        context = run_context(specialization())
        task, other = authorize_plan(LearningPlanDraft(steps=(draft_step(), draft_step('two'))),
                                     context, registry('teacher'))
        successful = task_result(task, 'SUCCEEDED', output=WorkerOutput(kind='EXPLANATION', content='Usable worker'))
        failed = task_result(other, 'FAILED', code='worker_failed')
        partial = successful.model_copy(update={'fields': {**successful.fields,
            'findings': failed.fields['findings']}})
        response = LearningResponse(kind='FAILURE', content='No usable final response')
        for results in ((successful, failed), (partial,)):
            with self.subTest(results=results):
                checked = check_final_response(response, context, results,
                    review=SemanticReview(verdict='ACCEPT', reason='Failure is appropriate'))
                self.assertEqual(checked, response)

    def test_final_synthesis_cannot_claim_proposal_without_one(self):
        context = run_context(specialization())
        task = authorize_plan(LearningPlanDraft(steps=(draft_step(),)), context, registry("teacher"))[0]
        result = task_result(task, "SUCCEEDED", output=WorkerOutput(kind="EXPLANATION", content="Synthetic"))
        response = LearningResponse(kind="PROPOSAL", content="Synthetic explanation")
        checked = check_final_response(response, context, (result,),
                                       review=SemanticReview(verdict="ACCEPT", reason="Checked"))
        self.assertEqual(checked.kind, "FAILURE")
        clarification = LearningResponse(kind="CLARIFICATION", content="Need more evidence")
        self.assertEqual(check_final_response(clarification, context, (result,),
                                             review=SemanticReview(verdict="ACCEPT", reason="Checked")), clarification)

    def test_curator_support_material_is_not_a_change_proposal(self):
        profile = specialization("CURATOR", "curator")
        context = run_context(profile, intent="CURATE")
        proposal = ProposedChange(targets=(context.snapshot.context.ref,), candidates=(), explanation="Candidato")
        review = SemanticReview(verdict="ACCEPT", reason="Controllato")

        def task(expected_output, run=context):
            draft = LearningStepDraft(
                step=PlanStep(id="curate", agent="curator", task="Prepara un sussidio"),
                specialization=profile.ref, intent="CURATE", expected_output=expected_output,
            )
            return authorize_plan(LearningPlanDraft(steps=(draft,)), run, registry("curator"))[0]

        support = task("SUPPORT_MATERIAL")
        accepted = check_worker_output(support, WorkerOutput(kind="SUPPORT_MATERIAL", content="Riassunto"),
                                       context, review=review)
        self.assertEqual(accepted.type, "TaskResult")
        self.assertEqual(accepted.fields["status"], "SUCCEEDED")
        self.assertEqual(accepted.fields["content"], "Riassunto")
        rejected = check_worker_output(support, WorkerOutput(kind="SUPPORT_MATERIAL", content="Riassunto",
                                                              proposals=(proposal,)), context, review=review)
        self.assertEqual(rejected.fields["status"], "FAILED")
        self.assertEqual(rejected.fields["findings"][0]["code"], "R16")
        with self.assertRaisesRegex(ValueError, "PREPARATION"):
            task("CHANGE_PROPOSAL")
        prep_root = context.snapshot.context.model_copy(update={"fields": {
            **context.snapshot.context.fields, "mode": "PREPARATION", "status": "DRAFT"}})
        prep = replace(context, snapshot=replace(context.snapshot, context=prep_root))
        self.assertEqual(check_worker_output(task("CHANGE_PROPOSAL", prep),
                                             WorkerOutput(kind="CHANGE_PROPOSAL", content="Proposta", proposals=(proposal,)),
                                             prep, review=review).fields["status"], "SUCCEEDED")

    def test_received_text_is_not_success_without_semantic_acceptance(self):
        context = run_context(specialization())
        task = authorize_plan(LearningPlanDraft(steps=(draft_step(),)), context, registry("teacher"))[0]
        output = WorkerOutput(kind="EXPLANATION", content="Testo plausibile")
        result = check_worker_output(task, output, context, review=SemanticReview(verdict="REJECT", reason="Non pertinente"))
        self.assertEqual(result.fields["status"], "FAILED")
        self.assertNotIn("content", result.fields)

    def build(self, steps, *, reject=False, budget=None):
        context = run_context(specialization())
        reg = registry("teacher")
        self.worker_prompts, self.lead_prompts = [], []
        owner = self
        class Lead:
            def __init__(self, **kwargs):
                self.values = kwargs
            def kickoff(self, prompt, response_format=None):
                owner.lead_prompts.append(prompt)
                if response_format is LearningPlanDraft:
                    value = LearningPlanDraft(steps=steps)
                elif response_format is SemanticReview:
                    denied = reject and "BAD_OUTPUT" in prompt
                    value = SemanticReview(verdict="REJECT" if denied else "ACCEPT", reason="Controllato")
                else:
                    value = LearningResponse(kind="ANSWER", content="Risposta finale")
                return SimpleNamespace(pydantic=value)
        def worker(config, task):
            self.worker_prompts.append(task)
            payload = json.loads(task.split("\nDATI_TASK\n", 1)[1])
            content = "BAD_OUTPUT" if payload["step_id"] == "one" else "Risultato indipendente"
            return WorkerOutput(kind="EXPLANATION", content=content)
        orchestrator = Orchestrator(lead_llm="llm", registry=reg,
            task_tool=TaskTool(registry=reg, worker=worker, logger=logging.getLogger("test")),
            search=lambda *a, **k: self.fail("Unexpected retrieval"),
            settings=OrchestratorSettings(max_steps=6, max_context_chars=budget),
            logger=logging.getLogger("test"), agent_factory=Lead, lead_config=parse_agent_file(Path(__file__).resolve().parents[1]/'control/lead.md'), lead_skills=[])
        return orchestrator, context

    def test_failed_semantic_step_skips_dependent_but_runs_independent(self):
        orchestrator, context = self.build((draft_step(), draft_step("dependent", depends_on=("one",)), draft_step("independent")), reject=True)
        response = orchestrator.run(context.request, context=context)
        results = [e for e in orchestrator.last_records if e.type == "TaskResult"]
        self.assertEqual([e.fields["status"] for e in results], ["FAILED", "SKIPPED", "SUCCEEDED"])
        self.assertEqual(response.kind, "PARTIAL_RESULT")
        self.assertEqual(len(self.worker_prompts), 2)
        self.assertNotIn("BAD_OUTPUT", self.lead_prompts[-1])

    def test_required_contract_is_never_truncated(self):
        orchestrator, context = self.build((draft_step(),), budget=10)
        response = orchestrator.run(context.request, context=context)
        self.assertEqual(response.kind, "CLARIFICATION")
        self.assertEqual(self.lead_prompts, [])
        self.assertEqual(self.worker_prompts, [])

    def test_invalid_plan_has_no_execution(self):
        orchestrator, context = self.build((draft_step(depends_on=("one",)),))
        response = orchestrator.run(context.request, context=context)
        self.assertEqual(response.kind, "FAILURE")
        self.assertEqual(self.worker_prompts, [])

    def test_all_failed_has_no_synthesis(self):
        orchestrator, context = self.build((draft_step(),), reject=True)
        self.assertEqual(orchestrator.run(context.request, context=context).kind, "FAILURE")
        self.assertFalse(any("SINTESI_FINALE" in p for p in self.lead_prompts))
