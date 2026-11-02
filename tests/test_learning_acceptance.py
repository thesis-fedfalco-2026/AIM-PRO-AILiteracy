"""Executable ALM scenarios; provider verdicts are simulated, not pedagogical guarantees."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from document_search.backend import build_backend
from learning.assessment import derive_learning_state, derive_activity_status, validate_evaluation
from learning.context import LearningRequest
from learning.contracts import EntityRef
from learning.decisions import approval_valid
from learning.metamodel import load_contract
from learning.outputs import WorkerOutput, LearningResponse, SemanticReview, check_final_response, build_brief
from learning.planning import LearningPlanDraft, LearningStepDraft, authorize_plan
from learning.policies import TrustedPolicy
from learning.rules import answer_key_match, all_completed
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from learning.validation import check_readiness, validate_snapshot
from agent_system.plan import PlanStep, RetrievalRequest
from smoke import prepare_demo
from tests.learning_runtime import demo_orchestrator
from tests.learning_fixtures import record, ref
from tests.test_learning_assessment import assessment_bundle
from tests.test_learning_context import policy
from tests.test_learning_profiles import specialization, registry
from tests.test_learning_planning import run_context, draft_step
from tests.test_learning_validation import snapshot


class AcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=LearningStore(Path(self.temp.name)/'state.sqlite'); self.addCleanup(self.store.close)
        self.backend=build_backend({'SEARCH_BACKEND':'mock'}); self.addCleanup(self.backend.close)
        self.orchestrator=demo_orchestrator(self.backend.search_documents)
        self.service=prepare_demo(self.store,lambda:self.orchestrator)

    def ask(self, **changes):
        request=LearningRequest(request_id='request',context_ref=self.store.read_context('demo').ref,
            subject_key='learner',text='Explain deployment',topic_refs=(ref('Topic','deployment'),))
        return self.service.request(request.model_copy(update=changes))

    def assessment(self):
        self.store.seed(assessment_bundle(),owner='session')
        service=LearningService(self.store,load_contract(),policy(),Mock(side_effect=AssertionError('No provider needed')))
        evidence=service.submit('session','learner',EntityRef.model_validate(ref('ActivityDefinition','activity')),'4','attempt')
        context=service._context('session','learner')
        evaluation=record('Evaluation','eval',{'context':evidence.fields['context'],'evidence':[evidence.ref.model_dump()],
            'specification':ref('AssessmentSpecification','assessment'),'mode':'FORMAL','result':'Correct','reviewPayloadKey':'pending'})
        return service,evidence,context,evaluation

    def test_case01(self):
        before=self.store.read_context('demo')
        result=self.ask()
        self.assertEqual(result.kind,'ANSWER')
        self.assertEqual(result.citations[0].source.id,'technical-deployment-guide')
        self.assertEqual(self.store.read_context('demo'),before)
        self.assertEqual(len([e for e in self.orchestrator.test_events if e[0]=='worker']),1)

    def test_case02(self):
        profiles=(specialization(),specialization('TRAINER','trainer'),specialization('EVALUATOR','evaluator'))
        context=run_context(*profiles)
        tasks=authorize_plan(LearningPlanDraft(steps=(draft_step(),draft_step('practice','trainer','TRAINER'),
            draft_step('assess','evaluator','EVALUATOR'))),context,registry('teacher','trainer','evaluator'))
        self.assertEqual([t.record.fields['intent'] for t in tasks],['EXPLAIN','PRACTICE','ASSESS'])
        self.assertFalse(self.store.owned('demo','Evaluation'))

    def test_case03(self):
        profile=specialization('SOCRATIC','socratic')
        context=run_context(profile,intent='SOCRATIC_GUIDANCE')
        step=LearningStepDraft(step=PlanStep(id='guide',agent='socratic',task='One question'),specialization=profile.ref,
                              intent='SOCRATIC_GUIDANCE',expected_output='SOCRATIC_TURN')
        task=authorize_plan(LearningPlanDraft(steps=(step,)),context,registry('socratic'))[0]
        old=record('TaskResult','old',{'task':ref('WorkerTask','old'),'status':'SUCCEEDED','content':'SECRET_SOLUTION'})
        task=replace(task,step=task.step.model_copy(update={'depends_on':('old',)}))
        self.assertNotIn('SECRET_SOLUTION',build_brief(task,{'old':old},None))
        response=check_final_response(LearningResponse(kind='ANSWER',content='SECRET_SOLUTION'),context,(old,),
                                     review=SemanticReview(verdict='REJECT',reason='Solution'))
        self.assertNotIn('SECRET_SOLUTION',response.content)

    def test_case04(self):
        outcome=record('LearningOutcome','outcome',{'statement':'Understand','topics':[ref('Topic','topic')]})
        activity=record('ActivityDefinition','activity',{'instruction':'Explain','intent':'EXPLAIN','format':'EXPOSITION','outcomes':[outcome.ref.model_dump()]})
        prerequisite=record('Prerequisite','required',{'dependent':activity.ref.model_dump(),'requiredTarget':outcome.ref.model_dump(),'kind':'MANDATORY'})
        self.assertTrue(any(f.severity=='BLOCKING' for f in check_readiness(snapshot(outcome,activity,prerequisite),activity.ref,'interact')))
        prerequisite=prerequisite.model_copy(update={'fields':{**prerequisite.fields,'kind':'RECOMMENDED'}})
        self.assertEqual([f.severity for f in check_readiness(snapshot(outcome,activity,prerequisite),activity.ref,'interact')],['WARNING'])

    def test_case05(self):
        from learning.policies import TrustedPolicy
        from learning.outputs import discovered_resources, ProposedChange
        from learning.planning import Capability
        from document_search.contracts import resource_key
        from types import SimpleNamespace
        trusted=self.service.policy.model_dump()
        trusted['subjects']['admin']['actions']['prep']=['bootstrap','read','interact','propose','decide','apply']
        trusted['scopes']['discovery']={'contexts':['prep'],'subjects':['admin'],'sources':['demo']}
        capability=Capability(capability='search_documents',accessPath='ORCHESTRATOR_RETRIEVAL',operations=('read',),scope='discovery',purpose='Discover')
        profile=record('AgentSpecialization','curator-prep',{'registryName':'resource-candidate-researcher','category':'CURATOR','role':'CURATOR','skills':['evidence-search'],
            'topics':[ref('Topic','prep-topic')],'competenceScope':'Demo','capabilities':[capability.model_dump(mode='json')],'skills':['evidence-search']})
        prep=LearningService(self.store,load_contract(),TrustedPolicy.model_validate(trusted),lambda:engine)
        root=prep.bootstrap('prep','admin')
        topic=record('Topic','prep-topic',{'name':'Demo','definition':'Demo'})
        model=record('DomainModel','prep-model',{'name':'Preparation','scope':'Demo','topics':[topic.ref.model_dump()],'definitions':[profile.ref.model_dump()]})
        updated=record(root.type,root.id,{**root.fields,'models':[model.ref.model_dump()]},'2')
        proposal=prep.propose('prep','admin',(root.ref,),(topic,profile,model,updated),'Curator model')
        prep.decide('prep','admin',proposal.ref,'APPROVE','Reviewed'); prep.apply('prep','admin',proposal.ref,'prep-model')
        context=prep._context('prep','admin')
        draft=LearningStepDraft(step=PlanStep(id='find',agent='resource-candidate-researcher',task='Find material',retrieval=RetrievalRequest(tool='search_documents',query='deployment',k=3)),
            specialization=profile.ref,intent='CURATE',expected_output='CHANGE_PROPOSAL',required_capabilities=(capability,))
        task=authorize_plan(LearningPlanDraft(steps=(draft,)),context,self.orchestrator.registry)[0]
        discovered=self.backend.search_documents('deployment',3,scope=task.search_scope)
        discovered['documents']=discovered['documents'][:1]
        discovered['documents'][0]['metadata']['resource_key']=resource_key('new-material','1')
        resources=discovered_resources(task,discovered)
        engine=SimpleNamespace(last_records=(),last_proposals=[(task.record.ref,ProposedChange(targets=(context.snapshot.context.ref,),candidates=resources,explanation='Discovered candidate'))],
            run=lambda *a,**k:LearningResponse(kind='ANSWER',content='Candidate material; not approved for learning.'))
        response=prep.request(LearningRequest(request_id='discover',context_ref=context.snapshot.context.ref,subject_key='admin',text='Find',intent='CURATE'))
        self.assertEqual(response.application_status,'pending')
        resource=self.store.candidates(response.proposal_refs[0])[0]
        self.assertFalse(resource.ref in self.service._context('demo','learner').snapshot.entities)
        learning_root=self.store.read_context('demo')
        binding=record('ResourceBinding','new-binding',{'context':learning_root.ref.model_dump(),'resource':resource.ref.model_dump(),'usageScope':'lesson','valid':True,'reviewPayloadKey':'pending'})
        learning_model=self.service._context('demo','admin').snapshot.get(ref('DomainModel','demo-model'))
        revised_model=record(learning_model.type,learning_model.id,{**learning_model.fields,'topics':[*learning_model.fields['topics'],topic.ref.model_dump()],'definitions':[*learning_model.fields['definitions'],resource.ref.model_dump()]},'2')
        revised_root=record(learning_root.type,learning_root.id,{**learning_root.fields,'models':[revised_model.ref.model_dump()],
            'resourceBindings':[*learning_root.fields['resourceBindings'],binding.ref.model_dump()]},'3')
        proposed=self.service.propose('demo','admin',(learning_root.ref,),(topic,resource,binding,revised_model,revised_root),'Explicit import and binding')
        self.assertFalse(approval_valid(binding,self.service._context('demo','admin').snapshot,self.service.policy))
        self.service.decide('demo','admin',proposed.ref,'APPROVE','Material and conditions reviewed')
        self.service.apply('demo','admin',proposed.ref,'import')
        active=self.service._context('demo','admin')
        self.assertTrue(approval_valid(active.snapshot.get(binding.ref),active.snapshot,active.policy))
        self.assertNotIn(resource_key(resource.id,resource.version),active.policy.scopes['lesson'].resources)

    def test_case06(self):
        context=run_context(specialization())
        with self.assertRaises(ValueError):
            authorize_plan(LearningPlanDraft(steps=(draft_step(),)),context,registry('teacher',tools=('write_database',)))

    def test_case07(self):
        _,_,context,evaluation=self.assessment()
        state=derive_learning_state(context,evaluation,{})
        self.assertEqual((state.fields['progress'],state.fields['verification']),('IN_PROGRESS','UNVERIFIED'))

    def test_case08(self):
        original=self.orchestrator._call
        def broken(prompt,model):
            if model is LearningPlanDraft:
                draft=original(prompt,model); item=draft.steps[0]
                return LearningPlanDraft(steps=(item.model_copy(update={'step':item.step.model_copy(update={'depends_on':('missing',)})}),))
            return original(prompt,model)
        self.orchestrator._call=broken
        self.assertEqual(self.ask().kind,'FAILURE')
        self.assertFalse(any(e[0]=='worker' for e in self.orchestrator.test_events))

    def test_case09(self):
        from tests.test_learning_outputs import OutputsTest
        harness=OutputsTest()
        orchestrator,context=harness.build((draft_step(),draft_step('dependent',depends_on=('one',)),draft_step('independent')),reject=True)
        result=orchestrator.run(context.request,context=context)
        self.assertEqual(result.kind,'PARTIAL_RESULT')
        self.assertEqual([r.fields['status'] for r in orchestrator.last_records if r.type=='TaskResult'],['FAILED','SKIPPED','SUCCEEDED'])
        self.assertNotIn('BAD_OUTPUT',harness.lead_prompts[-1])

    def test_case10(self):
        root=self.store.read_context('demo')
        proposals=[]
        for key in ('a','b'):
            topic=record('Topic',key,{'name':key,'definition':'New'})
            p=self.service.propose('demo','admin',(root.ref,),(topic,),key)
            self.service.decide('demo','admin',p.ref,'APPROVE','Reviewed'); proposals.append(p)
        self.service.apply('demo','admin',proposals[0].ref,'first')
        with self.assertRaises(StateConflict): self.service.apply('demo','admin',proposals[1].ref,'second')
        self.assertEqual(next(p for p in self.store.owned('demo','ChangeProposal') if p.id==proposals[1].id).fields['status'],'STALE')

    def test_case11(self):
        service,evidence,context,_=self.assessment()
        root=context.snapshot.context
        other_learner=record('Participant','learner-second',{'subjectKey':'learner','roles':['LEARNER']})
        second=record('ExecutionContext','session-second',{**root.fields,'participants':[other_learner.ref.model_dump()],
                      'activityOccurrences':[],'learningStates':[]})
        self.store.seed((other_learner,second),owner=second.id)
        self.assertEqual(second.fields['models'],root.fields['models'])
        self.assertEqual(self.store.read_context(second.id),second)
        with self.assertRaises(ValueError): self.store.read(evidence.ref,owner=second.id)
        self.assertTrue(self.store.read_context('session').fields['activityOccurrences'])
        self.assertFalse(self.store.read_context(second.id).fields['activityOccurrences'])

    def test_case12(self):
        self.assertEqual(self.ask().kind,'ANSWER')
        self.assertNotIn('learningDesign',self.store.read_context('demo').fields)
        with self.assertRaises(ValueError): self.service.submit('demo','learner',EntityRef.model_validate(ref('ActivityDefinition','missing')),'Response','attempt')
        self.assertFalse(self.store.owned('demo','LearningEvidence'))

    def test_case13(self):
        outcome=record('LearningOutcome','outcome',{'statement':'Understand','topics':[ref('Topic','topic')]})
        unit=record('ProcessNode','unit',{'name':'Unit','kind':'UNIT','outcomes':[outcome.ref.model_dump()]})
        snap=snapshot(outcome,unit)
        self.assertFalse(validate_snapshot(snap))
        self.assertTrue(check_readiness(snap,unit.ref,'interact'))

    def test_case14(self):
        context=run_context(specialization())
        with self.assertRaises(ValueError): authorize_plan(LearningPlanDraft(steps=(draft_step(),)),context,registry('other'))

    def test_case15(self):
        _,_,context,evaluation=self.assessment()
        state=derive_learning_state(context,evaluation,{EntityRef.model_validate(ref('RuleDefinition','achievement')):answer_key_match})
        self.assertEqual(state.fields['progress'],'ACQUIRED')
        self.assertEqual(state.fields['verification'],'PENDING_CONFIRMATION')
        self.assertFalse(approval_valid(evaluation,context.snapshot,context.policy))

    def test_case16(self):
        def completion(identity,inputs):
            return record('RuleDefinition',identity,{'purpose':'All completed','inputs':inputs,'condition':'All completed',
                'outcome':'Completed','unknownBehavior':'UNKNOWN','approvalRequirement':'Policy'})
        outcome=record('LearningOutcome','o',{'statement':'Do','topics':[ref('Topic','topic')]})
        activities=[record('ActivityDefinition',key,{'instruction':key,'intent':'PRACTICE','format':'GUIDED_DIALOGUE',
                    'outcomes':[outcome.ref.model_dump()]}) for key in ('a','b')]
        rules=[completion('rule-'+a.id,[a.id]) for a in activities]
        units=[record('ProcessNode','unit-'+a.id,{'name':a.id,'kind':'UNIT','activities':[a.ref.model_dump()],
                    'outcomes':[outcome.ref.model_dump()],'completionRule':rule.ref.model_dump()}) for a,rule in zip(activities,rules)]
        phase_rule=completion('phase-rule',[u.id for u in units])
        phase=record('ProcessNode','phase',{'name':'Independent','kind':'PHASE','composition':'INDEPENDENT',
                    'children':[u.ref.model_dump() for u in units],'outcomes':[outcome.ref.model_dump()],
                    'completionRule':phase_rule.ref.model_dump()})
        occurrences=[record('ActivityOccurrence','occ-'+a.id,{'context':ref('ExecutionContext','session'),'learner':ref('Participant','learner'),
            'activity':a.ref.model_dump(),'processNode':u.ref.model_dump(),'attemptKey':a.id,
            'status':'COMPLETED' if a.id=='a' else 'IN_PROGRESS'}) for a,u in zip(activities,units)]
        snap=snapshot(*rules,phase_rule,outcome,*activities,*units,phase,*occurrences)
        root=snap.context.model_copy(update={'fields':{**snap.context.fields,'activityOccurrences':[o.ref.model_dump() for o in occurrences]}})
        snap=replace(snap,context=root)
        bindings={r.ref:all_completed for r in (*rules,phase_rule)}
        learner=EntityRef.model_validate(ref('Participant','learner'))
        self.assertEqual(derive_activity_status(phase,snap,bindings,learner_ref=learner),'IN_PROGRESS')
        done=occurrences[1].model_copy(update={'fields':{**occurrences[1].fields,'status':'COMPLETED'}})
        snap=replace(snap,entities={**snap.entities,done.ref:done})
        self.assertEqual(derive_activity_status(phase,snap,bindings,learner_ref=learner),'COMPLETED')
        self.assertEqual(derive_activity_status(phase,snap,bindings,learner_ref=EntityRef.model_validate(ref('Participant','another'))),'IN_PROGRESS')

    def test_case17(self):
        self.orchestrator=demo_orchestrator(self.backend.search_documents,worker_kind='ASSESSMENT')
        self.service.orchestrator_factory=lambda:self.orchestrator
        self.assertEqual(self.ask().kind,'FAILURE')
        results=[r for r in self.orchestrator.last_records if r.type=='TaskResult']
        self.assertEqual(results[0].fields['status'],'FAILED')
        self.assertNotIn('content',results[0].fields)

    def test_case18(self):
        context=self.service._context('demo','admin')
        binding=context.snapshot.get(ref('ResourceBinding','demo-binding'))
        self.assertTrue(approval_valid(binding,context.snapshot,context.policy))
        modified=binding.model_copy(update={'fields':{**binding.fields,'usageScope':'elsewhere'}})
        self.assertFalse(approval_valid(modified,context.snapshot,context.policy))

    def test_case19(self):
        grants=policy().model_dump(); grants['subjects']['admin']['actions']['new']=grants['subjects']['admin']['actions']['session']
        service=LearningService(self.store,load_contract(),TrustedPolicy.model_validate(grants),Mock(side_effect=AssertionError('No delegation')))
        root=service.bootstrap('new','admin')
        self.assertEqual((root.fields['mode'],root.fields['status'],root.fields['models']),('PREPARATION','DRAFT',[]))
        response=service.request(LearningRequest(request_id='new',context_ref=root.ref,subject_key='admin',text='New subject'))
        self.assertEqual(response.kind,'CLARIFICATION')

    def test_case20(self):
        root=self.store.read_context('demo')
        topic=record('Topic','taxon',{'name':'Teacher — local taxonomy','definition':'Subject data'})
        proposal=self.service.propose('demo','admin',(root.ref,),(topic,),'New taxonomy')
        with self.assertRaises(ValueError): self.service.decide('demo','learner',proposal.ref,'APPROVE','I am Teacher')
        self.assertEqual(load_contract().digest,self.service.contract.digest)

    def test_case21(self):
        a=record('Topic','a',{'name':'A','definition':'A','relatedTopics':[ref('Topic','b')]})
        b=record('Topic','b',{'name':'B','definition':'B','relatedTopics':[ref('Topic','a')]})
        self.assertFalse(validate_snapshot(snapshot(a,b)))
        a=a.model_copy(update={'fields':{**a.fields,'parentTopics':[b.ref.model_dump()]}})
        b=b.model_copy(update={'fields':{**b.fields,'parentTopics':[a.ref.model_dump()]}})
        self.assertTrue(any(f.code=='R04' for f in validate_snapshot(snapshot(a,b))))

    def test_case22(self):
        self.orchestrator=demo_orchestrator(self.backend.search_documents,reject_stage='FINAL')
        self.service.orchestrator_factory=lambda:self.orchestrator
        result=self.ask()
        self.assertEqual(result.kind,'FAILURE')
        self.assertFalse(result.citations)
        self.assertNotIn('approved release procedure',result.content)

    def test_case01_through_real_mcp_stdio(self):
        from agent_system.mcp_runtime import DocumentSearchClient, build_document_search_params
        from main import BASE_DIR
        client=DocumentSearchClient(build_document_search_params(BASE_DIR,{'SEARCH_BACKEND':'mock'}))
        self.orchestrator=demo_orchestrator(client.search)
        self.service.orchestrator_factory=lambda:self.orchestrator
        result=self.ask()
        self.assertEqual(result.kind,'ANSWER')
        self.assertEqual(result.citations[0].source.id,'technical-deployment-guide')
        self.assertFalse(self.store.read_context('demo').fields['learningStates'])
