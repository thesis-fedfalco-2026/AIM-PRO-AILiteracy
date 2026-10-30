from agent_system.config import parse_agent_file
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
                profile="local",
                tools=("search_documents",),
                system_prompt="Research.",
                source=Path("researcher.md"),
            ),
            AgentConfig(
                name="writer",
                description="Writes answers.",
                profile="local",
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
    def build(self, *, failure=None, budget=None, plan_override=None):
        from dataclasses import replace
        from learning.outputs import WorkerOutput, LearningResponse, SemanticReview
        from learning.planning import LearningPlanDraft, Capability
        from learning.policies import ScopeGrant
        from tests.test_learning_planning import run_context, draft_step
        from tests.test_learning_profiles import specialization, registry
        self.events, self.prompts = [], []
        capability = Capability(capability='search_documents',accessPath='ORCHESTRATOR_RETRIEVAL',operations=('read',),scope='demo',purpose='Evidence')
        profile = specialization(capabilities=(capability.model_dump(mode='json'),))
        context = run_context(profile)
        root = context.snapshot.context.model_copy(update={'fields':{**context.snapshot.context.fields,'mode':'PREPARATION'}})
        context = replace(context,snapshot=replace(context.snapshot,context=root),policy=context.policy.model_copy(update={
            'scopes':{'demo':ScopeGrant(contexts=['session'],subjects=['learner'],sources=['demo'])}}))
        one = draft_step().model_copy(update={'step':PlanStep(id='one',agent='teacher',task='Find evidence',retrieval=RetrievalRequest(tool='search_documents',query='deployment',k=3)), 'required_capabilities':(capability,)})
        plan = LearningPlanDraft(steps=(one,draft_step('dependent',depends_on=('one',)),draft_step('independent')))
        owner=self
        class Lead:
            def kickoff(self,prompt,response_format=None):
                owner.prompts.append(prompt)
                if response_format is LearningPlanDraft:
                    value = plan_override if plan_override is not None else plan
                elif response_format is SemanticReview:
                    value = SemanticReview(verdict='ACCEPT',reason='Checked')
                else:
                    owner.events.append('synthesis')
                    if failure == 'synthesis': raise RuntimeError('private provider text')
                    value = LearningResponse(kind='ANSWER',content='Checked answer')
                return SimpleNamespace(pydantic=value)
        def search(query,k,*,scope):
            owner.events.append('search')
            if failure == 'search': raise RuntimeError('private source text')
            owner.assertEqual(scope.source_scope_keys,('demo',))
            return {'documents':[]}
        def worker(config,brief):
            import json
            data=json.loads(brief.split('\nDATI_TASK\n')[1]); step=data['step_id']
            owner.events.append(step)
            if failure == 'worker' and step == 'one': raise RuntimeError('private worker text')
            return WorkerOutput(kind='EXPLANATION',content='Evidence checked')
        reg=registry('teacher','trainer',tools=('search_documents',))
        orchestration=Orchestrator(lead_llm='llm',registry=reg,
            task_tool=TaskTool(registry=reg,worker=worker,logger=logging.getLogger('test')),
            search=search,settings=OrchestratorSettings(max_steps=6,max_context_chars=budget),logger=logging.getLogger('test'),
            agent_factory=lambda **k:Lead(), lead_config=parse_agent_file(Path(__file__).resolve().parents[1]/'control/lead.md'), lead_skills=[])
        return orchestration,context

    def test_executes_in_stable_order(self):
        import json
        orchestration,context=self.build()
        self.assertEqual(orchestration.run(context.request,context=context).kind,'ANSWER')
        self.assertEqual(self.events,['search','one','dependent','independent','synthesis'])
        lead_data=json.loads(self.prompts[0].split('DATI\n',1)[1])
        self.assertEqual(lead_data['workers'],[{'name':'teacher','description':'[teacher] teacher'}])
        self.assertIn('kind ANSWER',next(prompt for prompt in self.prompts if prompt.startswith('SINTESI_FINALE')))

    def test_lead_prompt_requires_capability_for_retrieval(self):
        orchestration,context=self.build()
        orchestration.run(context.request,context=context)
        instruction=self.prompts[0].split('\nCONTRATTO\n',1)[0]
        for part in ('retrieval', 'required_capabilities', 'search_documents',
                     'ORCHESTRATOR_RETRIEVAL', 'read', 'scope', 'ActivityDefinition',
                     'intent', 'activities vuoto', 'LearningOutcome', 'coverage vuoto'):
            with self.subTest(part=part):
                self.assertIn(part,instruction)

    def test_plan_and_worker_ids_do_not_collide_when_step_is_named_plan(self):
        from learning.planning import LearningPlanDraft
        from tests.test_learning_planning import draft_step
        orchestration,context=self.build(plan_override=LearningPlanDraft(steps=(draft_step('plan'),)))
        orchestration.run(context.request,context=context)
        ids=[record.id for record in orchestration.last_records]
        self.assertEqual(len(ids),len(set(ids)))

    def test_preparation_teacher_retrieval_does_not_create_resource_proposal(self):
        orchestration,context=self.build()
        orchestration.search=lambda *args, **kwargs: {'documents':[{'text':'Source text','metadata':{
            'source_scope':'demo','resource_key':'["source","1"]','source':'demo-document'}}]}
        self.assertEqual(orchestration.run(context.request,context=context).kind,'ANSWER')
        self.assertEqual(orchestration.last_proposals,[])

    def test_preparation_citations_work_without_granting_resource_proposal_role(self):
        from dataclasses import replace
        import json
        from learning.outputs import Citation, LearningResponse, ProposedChange, SemanticReview, WorkerOutput
        from learning.planning import Capability, LearningPlanDraft, LearningStepDraft
        from learning.policies import ScopeGrant
        from tests.learning_fixtures import record, ref
        from tests.test_learning_planning import run_context
        from tests.test_learning_profiles import specialization

        capability = Capability(capability='search_documents', accessPath='ORCHESTRATOR_RETRIEVAL',
            operations=('read',), scope='demo', purpose='Prepare from sources')
        citation = Citation(source=ref('Resource', 'source'), supportedClaim='Source supports this design')
        evidence = {'documents': [{'text': 'Source text', 'metadata': {
            'source_scope': 'demo', 'resource_key': '["source","1"]', 'source': 'demo-document'}}]}
        for role, name, intent, automatic_proposals in (
            ('EVALUATOR', 'assessment-designer', 'ASSESS', 0),
            ('CURATOR', 'resource-candidate-researcher', 'CURATE', 1),
        ):
            with self.subTest(worker=name):
                profile = specialization(role, name, (capability.model_dump(mode='json'),))
                context = run_context(profile, intent=intent)
                root = context.snapshot.context.model_copy(update={'fields': {
                    **context.snapshot.context.fields, 'mode': 'PREPARATION', 'status': 'DRAFT'}})
                context = replace(context, snapshot=replace(context.snapshot, context=root),
                    policy=context.policy.model_copy(update={'scopes': {
                        'demo': ScopeGrant(contexts=['session'], subjects=['learner'], sources=['demo'])}}))
                draft = LearningPlanDraft(steps=(LearningStepDraft(
                    step=PlanStep(id='prepare', agent=name, task='Prepare from sources',
                        retrieval=RetrievalRequest(tool='search_documents', query='topic', k=1)),
                    specialization=profile.ref, intent=intent, expected_output='CHANGE_PROPOSAL',
                    required_capabilities=(capability,)),))
                candidate = record('Topic', 'topic', {'name': 'Revised', 'definition': 'Proposal'}, '2')
                proposal = ProposedChange(targets=(candidate.ref.model_copy(update={'version': '1'}),),
                    candidates=(candidate,), explanation='Reviewed proposal')
                briefs = []
                class Lead:
                    def kickoff(self, prompt, response_format=None):
                        value = (draft if response_format is LearningPlanDraft else
                            SemanticReview(verdict='ACCEPT', reason='Checked') if response_format is SemanticReview else
                            LearningResponse(kind='ANSWER', content='Prepared design', citations=(citation,)))
                        return SimpleNamespace(pydantic=value)
                def worker(config, brief):
                    briefs.append(json.loads(brief.split('\nDATI_TASK\n', 1)[1]))
                    return WorkerOutput(kind='CHANGE_PROPOSAL', content='Prepared design',
                        citations=(citation,), proposals=(proposal,))
                reg = AgentRegistry((parse_agent_file(Path(__file__).resolve().parents[1]/'agents'/f'{name}.md'),))
                orchestration = Orchestrator(lead_llm='offline', registry=reg,
                    task_tool=TaskTool(registry=reg, worker=worker, logger=logging.getLogger('test')),
                    search=lambda *a, **k: evidence, settings=OrchestratorSettings(max_steps=6),
                    logger=logging.getLogger('test'), agent_factory=lambda **k: Lead(),
                    lead_config=parse_agent_file(Path(__file__).resolve().parents[1]/'control/lead.md'), lead_skills=[])
                response = orchestration.run(context.request, context=context)
                self.assertEqual(response.kind, 'ANSWER')
                self.assertEqual(response.citations, (citation,))
                self.assertEqual(briefs[0]['source_refs'], [
                    {'ref': ref('Resource', 'source'), 'resource_key': '["source","1"]'}])
                self.assertEqual(len(orchestration.last_proposals), 1 + automatic_proposals)
                self.assertEqual(orchestration.last_proposals[0][1], proposal)
                if automatic_proposals:
                    self.assertEqual(orchestration.last_proposals[1][1].candidates[0].ref, citation.source)

    def test_retrieval_failure_skips_dependent_but_runs_independent(self):
        orchestration,context=self.build(failure='search')
        self.assertEqual(orchestration.run(context.request,context=context).kind,'PARTIAL_RESULT')
        self.assertEqual(self.events,['search','independent','synthesis'])

    def test_worker_failure_skips_dependent_but_runs_independent(self):
        orchestration,context=self.build(failure='worker')
        self.assertEqual(orchestration.run(context.request,context=context).kind,'PARTIAL_RESULT')
        self.assertEqual(self.events,['search','one','independent','synthesis'])
        self.assertNotIn('private worker text',self.prompts[-1])

    def test_wrong_plan_never_reaches_tools(self):
        orchestration,context=self.build(plan_override=ExecutionPlan())
        self.assertEqual(orchestration.run(context.request,context=context).kind,'FAILURE')
        self.assertEqual(self.events,[])

    def test_synthesis_failure_is_safe_failure(self):
        orchestration,context=self.build(failure='synthesis')
        result=orchestration.run(context.request,context=context)
        self.assertEqual(result.kind,'FAILURE')
        self.assertNotIn('private',result.content)

    def test_required_contract_is_not_truncated(self):
        orchestration,context=self.build(budget=20)
        self.assertEqual(orchestration.run(context.request,context=context).kind,'CLARIFICATION')
        self.assertEqual(self.prompts,[])
