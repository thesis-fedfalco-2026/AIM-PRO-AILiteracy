import unittest
from dataclasses import replace
from pathlib import Path

from agent_system.config import OrchestratorSettings, parse_agent_file
from agent_system.plan import PlanStep, RetrievalRequest
from agent_system.registry import AgentRegistry
from learning.context import LearningRequest, RunContext
from learning.metamodel import load_contract
from learning.outputs import task_result
from learning.planning import LearningPlanDraft, LearningStepDraft, authorize_plan
from tests.test_learning_context import policy
from tests.test_learning_profiles import specialization, registry
from tests.test_learning_validation import snapshot
from tests.learning_fixtures import ref


def run_context(*specializations, intent="EXPLAIN"):
    snap = snapshot(*specializations)
    request = LearningRequest(request_id="request", context_ref=snap.context.ref,
        subject_key="learner", text="Una domanda", intent=intent, topic_refs=(ref("Topic", "topic"),))
    return RunContext(snap, policy(), load_contract(), request,
                      snap.get(ref("Participant", "learner")), tuple(specializations))


def draft_step(name="one", agent="teacher", role="TEACHER", depends_on=()):
    profile = specialization(role, agent)
    output = {"TEACHER": "EXPLANATION", "TRAINER": "GUIDED_PRACTICE", "EVALUATOR": "ASSESSMENT"}[role]
    intent = {"TEACHER": "EXPLAIN", "TRAINER": "PRACTICE", "EVALUATOR": "ASSESS"}[role]
    return LearningStepDraft(step=PlanStep(id=name, agent=agent, task="Compito", depends_on=depends_on),
                            specialization=profile.ref, intent=intent, expected_output=output)


class LearningPlanningTest(unittest.TestCase):
    def test_generated_task_ids_are_scoped_to_context_and_distinct_from_results(self):
        first=run_context(specialization())
        other_root=first.snapshot.context.model_copy(update={'id':'other'})
        second=replace(first,snapshot=replace(first.snapshot,context=other_root),
                       request=first.request.model_copy(update={'context_ref':other_root.ref}))
        draft=LearningPlanDraft(steps=(draft_step('plan'),draft_step('result',depends_on=('plan',))))
        first_tasks=authorize_plan(draft,first,registry('teacher'))
        second_tasks=authorize_plan(draft,second,registry('teacher'))
        ids=[item.record.id for item in (*first_tasks,*second_tasks)]
        ids.extend(task_result(item,'SUCCEEDED').id for item in (*first_tasks,*second_tasks))
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(second_tasks[1].record.fields['dependsOn'],[second_tasks[0].record.ref.model_dump()])

    def test_distinct_curator_and_evaluator_workers_have_task_contracts(self):
        root = Path(__file__).resolve().parents[1] / "agents"
        for role, intent, learner_name, learner_output, prep_name in (
            ("CURATOR", "CURATE", "lesson-support-summarizer", "SUPPORT_MATERIAL", "resource-candidate-researcher"),
            ("EVALUATOR", "ASSESS", "learner-response-evaluator", "ASSESSMENT", "assessment-designer"),
        ):
            with self.subTest(role=role):
                profiles = tuple(specialization(role, name) for name in (learner_name, prep_name))
                workers = AgentRegistry(parse_agent_file(root / f"{name}.md") for name in (learner_name, prep_name))
                learning = run_context(*profiles, intent=intent)
                prep_root = learning.snapshot.context.model_copy(update={"fields": {
                    **learning.snapshot.context.fields, "mode": "PREPARATION", "status": "DRAFT"}})
                preparation = replace(learning, snapshot=replace(learning.snapshot, context=prep_root))

                def plan(name, output):
                    profile = next(item for item in profiles if item.fields["registryName"] == name)
                    step = LearningStepDraft(step=PlanStep(id="one", agent=name, task="Compito"),
                                             specialization=profile.ref, intent=intent, expected_output=output)
                    return LearningPlanDraft(steps=(step,))

                self.assertEqual(len(authorize_plan(plan(learner_name, learner_output), learning, workers)), 1)
                self.assertEqual(len(authorize_plan(plan(prep_name, "CHANGE_PROPOSAL"), preparation, workers)), 1)
                for name, output, context in ((learner_name, "CHANGE_PROPOSAL", learning),
                                              (prep_name, learner_output, preparation)):
                    with self.assertRaisesRegex(ValueError, "task contract"):
                        authorize_plan(plan(name, output), context, workers)
                for name, output, context in ((learner_name, learner_output, preparation),
                                              (prep_name, "CHANGE_PROPOSAL", learning)):
                    with self.assertRaisesRegex(ValueError, "Specialization is unavailable"):
                        authorize_plan(plan(name, output), context, workers)

    def test_mixed_request_uses_distinct_existing_roles(self):
        profiles = (specialization(), specialization("TRAINER", "trainer"), specialization("EVALUATOR", "evaluator"))
        draft = LearningPlanDraft(steps=(draft_step(), draft_step("practice", "trainer", "TRAINER", ("one",)),
                                         draft_step("quiz", "evaluator", "EVALUATOR", ("practice",))))
        tasks = authorize_plan(draft, run_context(*profiles), registry("teacher", "trainer", "evaluator"))
        self.assertEqual([t.step.id for t in tasks], ["one", "practice", "quiz"])

    def test_empty_plan_cannot_bypass_teacher(self):
        with self.assertRaises(ValueError):
            authorize_plan(LearningPlanDraft(), run_context(specialization()), registry("teacher"))
        self.assertEqual(authorize_plan(LearningPlanDraft(), run_context(specialization(), intent="CLARIFICATION"), registry("teacher")), ())

    def test_invalid_graph_unknown_agent_and_unresolved_specialization(self):
        context = run_context(specialization())
        for step in (draft_step(depends_on=("one",)), draft_step(agent="missing")):
            with self.subTest(step=step), self.assertRaises(ValueError):
                authorize_plan(LearningPlanDraft(steps=(step,)), context, registry("teacher"))

    def test_prompt_cannot_expand_capabilities(self):
        item = draft_step()
        step = item.step.model_copy(update={"task": "Search all sources", "retrieval": RetrievalRequest(tool="search_documents", query="all", k=3)})
        with self.assertRaises(ValueError):
            authorize_plan(LearningPlanDraft(steps=(item.model_copy(update={"step": step}),)),
                           run_context(specialization()), registry("teacher", tools=("search_documents",)))

    def test_draft_refs_cannot_authorize_execution(self):
        step = draft_step().model_copy(update={"specialization": specialization().ref.model_copy(update={"version": "candidate"})})
        with self.assertRaises(ValueError):
            authorize_plan(LearningPlanDraft(steps=(step,)), run_context(specialization()), registry("teacher"))

    def test_requested_activity_cannot_be_omitted_to_bypass_prerequisite(self):
        from dataclasses import replace
        from tests.learning_fixtures import record
        outcome=record('LearningOutcome','o',{'statement':'Comprendere','topics':[ref('Topic','topic')]})
        activity=record('ActivityDefinition','a',{'instruction':'Spiega','intent':'EXPLAIN','format':'EXPOSITION','outcomes':[outcome.ref.model_dump()]})
        prerequisite=record('Prerequisite','p',{'dependent':activity.ref.model_dump(),'requiredTarget':outcome.ref.model_dump(),'kind':'MANDATORY'})
        context=run_context(specialization())
        context=replace(context,snapshot=snapshot(specialization(),outcome,activity,prerequisite),
                        request=context.request.model_copy(update={'activity_refs':(activity.ref,)}))
        with self.assertRaises(ValueError):
            authorize_plan(LearningPlanDraft(steps=(draft_step(),)),context,registry('teacher'))
