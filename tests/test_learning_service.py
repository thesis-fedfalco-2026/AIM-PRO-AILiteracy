from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest
import sqlite3

from learning.contracts import EntityRef
from learning.context import LearningRequest
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore, canonical
from learning.outputs import LearningResponse, ProposedChange
from tests.test_learning_context import policy
from tests.test_learning_assessment import assessment_bundle
from tests.learning_fixtures import record, ref


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite'
        self.store = LearningStore(self.path); self.addCleanup(self.store.close)
        self.factory = Mock(side_effect=RuntimeError('provider private text'))
        self.service = LearningService(self.store, load_contract(), policy(), self.factory)

    def test_bootstrap_without_model(self):
        root = self.service.bootstrap('session', 'admin')
        self.assertEqual((root.fields['status'], root.fields['mode'], root.fields['models']), ('DRAFT', 'PREPARATION', []))
        self.assertEqual(self.service.show('session', 'admin')['context']['id'], 'session')
        self.factory.assert_not_called()

    def test_missing_policy_stops_without_delegation(self):
        self.store.seed(assessment_bundle(), owner='session')
        request = LearningRequest(request_id='req', context_ref=self.store.read_context('session').ref,
                                  subject_key='unknown', text='secret')
        with self.assertRaises(ValueError):
            self.service.request(request)
        self.factory.assert_not_called()

    def test_full_cycle_reopens(self):
        root = self.service.bootstrap('session', 'admin')
        topic = record('Topic', 'new-topic', {'name':'Demo', 'definition':'Synthetic'})
        model = record('DomainModel', 'new-model', {'name':'Demo', 'scope':'Demo', 'topics':[topic.ref.model_dump()]})
        updated = record('ExecutionContext', root.id, {**root.fields, 'models':[model.ref.model_dump()],
                         'status':'ACTIVE', 'mode':'LEARNING'}, version='2')
        proposal = self.service.propose('session', 'admin', (root.ref,), (topic,model,updated), 'Activate model')
        self.assertEqual(self.store.read_context('session').version, root.version)
        self.service.decide('session','admin',proposal.ref,'APPROVE','Content reviewed')
        self.assertEqual(self.store.read_context('session').version, root.version)
        change = self.service.apply('session','admin',proposal.ref,'apply')
        self.assertEqual(change.fields['newVersion'], '2')
        with LearningStore(self.path) as reopened:
            self.assertEqual(reopened.read_context('session').fields['mode'], 'LEARNING')
        self.factory.assert_not_called()

    def test_attempt_survives_provider_failure(self):
        self.store.seed(assessment_bundle(), owner='session')
        evidence = self.service.submit('session','learner',EntityRef.model_validate(ref('ActivityDefinition','activity')),'4','attempt')
        self.assertEqual(self.store.read(evidence.ref,owner='session').fields['contentOrLocator'],'4')
        self.factory.assert_not_called()

    def test_show_hides_answer_keys_and_other_learners(self):
        self.store.seed(assessment_bundle(), owner='session')
        result = self.service.show('session','learner')
        self.assertNotIn('answerKey', str(result))
        self.assertNotIn("'subjectKey': 'admin'", str(result))

    def test_no_specialization_returns_clarification_without_provider(self):
        self.store.seed(assessment_bundle(), owner='session')
        request = LearningRequest(request_id='req',context_ref=self.store.read_context('session').ref,
                                  subject_key='learner',text='Explain')
        result = self.service.request(request)
        self.assertEqual(result.kind, 'CLARIFICATION')
        self.factory.assert_not_called()

    def test_legacy_registry_reference_reports_migration(self):
        from smoke import prepare_demo
        from learning.planning import LegacyAgentReferenceError
        engine=Mock(last_records=(),last_proposals=())
        engine.run.side_effect=LegacyAgentReferenceError('learning-teacher')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        result=service.request(LearningRequest(request_id='legacy',context_ref=root.ref,
                                               subject_key='learner',text='Explain'))
        self.assertEqual(result.kind,'CLARIFICATION')
        self.assertIn('registryName',result.content)
        self.assertIn('migration',result.content)

    def test_neutral_turn_does_not_cancel_socratic_mode(self):
        from smoke import prepare_demo
        from learning.outputs import LearningResponse
        engine=Mock(last_records=(),last_proposals=())
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Which step would you try?')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        for index,intent in enumerate(('SOCRATIC_GUIDANCE','STATE','EXPLAIN')):
            result=service.request(LearningRequest(request_id=str(index),context_ref=root.ref,subject_key='learner',
                                   text='Same problem',problem_key='p',intent=intent))
        self.assertEqual(result.kind,'CLARIFICATION')
        self.assertEqual(engine.run.call_count,2)

    def test_failed_role_switch_does_not_cancel_socratic_mode(self):
        from smoke import prepare_demo
        from learning.outputs import LearningResponse
        engine=Mock(last_records=(),last_proposals=())
        engine.run.side_effect=[LearningResponse(kind='ANSWER',content='Which step?'),LearningResponse(kind='FAILURE',content='Provider unavailable')]
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        service.request(LearningRequest(request_id='guide',context_ref=root.ref,subject_key='learner',text='Help',problem_key='p',intent='SOCRATIC_GUIDANCE'))
        service.request(LearningRequest(request_id='switch',context_ref=root.ref,subject_key='learner',text='Explain',problem_key='p',switch_from_socratic=True))
        result=service.request(LearningRequest(request_id='retry',context_ref=root.ref,subject_key='learner',text='Explain',problem_key='p'))
        self.assertEqual(result.kind,'CLARIFICATION')
        self.assertEqual(engine.run.call_count,2)

    def test_socratic_mode_requires_explicit_key_for_distinct_problem(self):
        from smoke import prepare_demo
        from learning.outputs import LearningResponse
        engine=Mock(last_records=(),last_proposals=())
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Response')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        service.request(LearningRequest(request_id='guide',context_ref=root.ref,subject_key='learner',
                                        text='Help with problem A',problem_key='A',intent='SOCRATIC_GUIDANCE'))
        unkeyed=service.request(LearningRequest(request_id='unkeyed',context_ref=root.ref,
                                               subject_key='learner',text='Explain another topic'))
        distinct=service.request(LearningRequest(request_id='distinct',context_ref=root.ref,
                                                subject_key='learner',text='Explain another topic',problem_key='B'))
        self.assertEqual(unkeyed.kind,'CLARIFICATION')
        self.assertEqual(distinct.kind,'ANSWER')
        self.assertEqual(engine.run.call_count,2)

    def test_prior_answer_cannot_replay_after_socratic_mode_starts(self):
        from smoke import prepare_demo
        engine=Mock(last_records=(),last_proposals=())
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Synthetic answer')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        old=LearningRequest(request_id='old-answer',context_ref=root.ref,subject_key='learner',
                            text='Explain',problem_key='same')
        self.assertEqual(service.request(old).kind,'ANSWER')
        guide=old.model_copy(update={'request_id':'guide','intent':'SOCRATIC_GUIDANCE'})
        self.assertEqual(service.request(guide).kind,'ANSWER')
        self.assertEqual(service.request(old).kind,'CLARIFICATION')
        self.assertEqual(engine.run.call_count,2)

    def test_prior_model_failure_cannot_replay_content_after_socratic_mode(self):
        from smoke import prepare_demo
        engine=Mock(last_records=(),last_proposals=())
        engine.run.side_effect=[LearningResponse(kind='FAILURE',content='SECRET_SOLUTION'),
                                LearningResponse(kind='ANSWER',content='Guide')]
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        old=LearningRequest(request_id='old-failure',context_ref=root.ref,subject_key='learner',
                            text='Explain',problem_key='same')
        self.assertEqual(service.request(old).kind,'FAILURE')
        guide=old.model_copy(update={'request_id':'guide','intent':'SOCRATIC_GUIDANCE'})
        self.assertEqual(service.request(guide).kind,'ANSWER')
        replay=service.request(old)
        self.assertEqual(replay.kind,'CLARIFICATION')
        self.assertNotIn('SECRET_SOLUTION',replay.content)

    def test_successful_explicit_switch_releases_socratic_problem(self):
        from smoke import prepare_demo
        engine=Mock(last_records=(),last_proposals=())
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Synthetic answer')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        guide=LearningRequest(request_id='guide',context_ref=root.ref,subject_key='learner',
                              text='Guide',problem_key='same',intent='SOCRATIC_GUIDANCE')
        self.assertEqual(service.request(guide).kind,'ANSWER')
        switch=guide.model_copy(update={'request_id':'switch','intent':'EXPLAIN','switch_from_socratic':True})
        self.assertEqual(service.request(switch).kind,'ANSWER')
        unrelated=guide.model_copy(update={'request_id':'unrelated','intent':'EXPLAIN','problem_key':None})
        self.assertEqual(service.request(unrelated).kind,'ANSWER')

    def test_blank_problem_key_is_rejected(self):
        with self.assertRaises(ValueError):
            LearningRequest(request_id='blank',context_ref=EntityRef.model_validate(ref('ExecutionContext','session')),
                            subject_key='learner',text='Explain',problem_key='   ')

    def test_invalid_later_proposal_rolls_back_records_and_earlier_proposal(self):
        from smoke import prepare_demo
        task_ref=EntityRef.model_validate(ref('WorkerTask','probe'))
        result_record=record('TaskResult','probe-result',{'task':task_ref.model_dump(),
                                                       'status':'SUCCEEDED','content':'Synthetic'})
        engine=Mock(last_records=(result_record,),last_proposals=[])
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Synthetic')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        topic=record('Topic','probe-topic',{'name':'Probe','definition':'Synthetic'})
        engine.last_proposals=[(task_ref,ProposedChange(targets=(root.ref,),candidates=(topic,),explanation='Valid')),
                               (task_ref,ProposedChange(targets=(root.ref,),candidates=(),explanation='Invalid'))]
        before={e.id for e in self.store.owned('demo','ChangeProposal')}

        response=service.request(LearningRequest(request_id='atomic-invalid',context_ref=root.ref,
                                                 subject_key='admin',text='Probe'))

        self.assertEqual(response.kind,'FAILURE')
        self.assertEqual({e.id for e in self.store.owned('demo','ChangeProposal')},before)
        self.assertEqual(self.store.owned('demo','TaskResult'),())

    def test_final_write_failure_rolls_back_records_and_proposals(self):
        from smoke import prepare_demo
        task_ref=EntityRef.model_validate(ref('WorkerTask','probe'))
        result_record=record('TaskResult','probe-result',{'task':task_ref.model_dump(),
                                                       'status':'SUCCEEDED','content':'Synthetic'})
        engine=Mock(last_records=(result_record,),last_proposals=[])
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Synthetic')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        topic=record('Topic','probe-topic',{'name':'Probe','definition':'Synthetic'})
        engine.last_proposals=[(task_ref,ProposedChange(targets=(root.ref,),candidates=(topic,),explanation='Valid'))]
        before={e.id for e in self.store.owned('demo','ChangeProposal')}
        original_finish=self.store.finish_request
        calls=0

        def fail_first_finish(*args):
            nonlocal calls
            calls+=1
            if calls==1:
                raise sqlite3.OperationalError('injected final write failure')
            return original_finish(*args)

        with patch.object(self.store,'finish_request',side_effect=fail_first_finish):
            response=service.request(LearningRequest(request_id='atomic-write',context_ref=root.ref,
                                                     subject_key='admin',text='Probe'))

        self.assertEqual(response.kind,'FAILURE')
        self.assertEqual({e.id for e in self.store.owned('demo','ChangeProposal')},before)
        self.assertEqual(self.store.owned('demo','TaskResult'),())

    def test_successful_request_commits_once_and_replays(self):
        from smoke import prepare_demo
        task_ref=EntityRef.model_validate(ref('WorkerTask','success-task'))
        result_record=record('TaskResult','success-result',{'task':task_ref.model_dump(),
                                                         'status':'SUCCEEDED','content':'Synthetic'})
        engine=Mock(last_records=(result_record,),last_proposals=[])
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Synthetic')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        topic=record('Topic','success-topic',{'name':'Probe','definition':'Synthetic'})
        engine.last_proposals=[(task_ref,ProposedChange(targets=(root.ref,),candidates=(topic,),explanation='Valid'))]
        request=LearningRequest(request_id='atomic-success',context_ref=root.ref,subject_key='admin',text='Probe')

        first=service.request(request)
        second=service.request(request)

        self.assertEqual(first.kind,'PROPOSAL')
        self.assertEqual(second,first)
        self.assertEqual(engine.run.call_count,1)
        self.assertEqual(len(self.store.owned('demo','TaskResult')),1)
        self.assertEqual(len(self.store.candidates(first.proposal_refs[0])),1)
        with self.assertRaises(ValueError):
            service.request(request.model_copy(update={'text':'Different payload'}))

    def test_cleanup_failure_preserves_terminal_result_and_replay(self):
        from smoke import prepare_demo
        engine=Mock(last_records=(),last_proposals=())
        engine.close.side_effect=RuntimeError('PRIVATE cleanup detail')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        for failed in (False,True):
            with self.subTest(provider_failed=failed):
                engine.run.side_effect=RuntimeError('PRIVATE provider detail') if failed else None
                engine.run.return_value=LearningResponse(kind='ANSWER',content='Synthetic answer')
                request=LearningRequest(request_id=f'cleanup-{failed}',context_ref=root.ref,
                                        subject_key='learner',text='Explain')
                first=service.request(request)
                second=service.request(request)
                self.assertEqual(first.kind,'FAILURE' if failed else 'ANSWER')
                self.assertEqual(second,first)
                self.assertNotIn('PRIVATE',first.model_dump_json())
                self.assertIsNotNone(self.store.db.execute(
                    'SELECT result FROM requests WHERE owner=? AND id=?',('demo',request.request_id)).fetchone()[0])
        self.assertEqual(engine.run.call_count,2)

    def test_failed_final_response_cannot_be_promoted_to_proposal(self):
        from smoke import prepare_demo
        from learning.outputs import check_final_response, SemanticReview
        task_ref=EntityRef.model_validate(ref('WorkerTask','checked-worker'))
        result_record=record('TaskResult','checked-result',{'task':task_ref.model_dump(),
                                                         'status':'SUCCEEDED','content':'Reviewed worker'})
        failed_record=record('TaskResult','failed-result',{'task':ref('WorkerTask','failed-worker'),
                                                        'status':'FAILED'})
        engine=Mock(last_records=(result_record,failed_record),last_proposals=[])
        engine.run.side_effect=lambda request, *, context: check_final_response(
            LearningResponse(kind='FAILURE',content='No usable final response'),context,engine.last_records,
            review=SemanticReview(verdict='ACCEPT',reason='Failure is appropriate'))
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        topic=record('Topic','unpublished-topic',{'name':'Probe','definition':'Synthetic'})
        engine.last_proposals=[(task_ref,ProposedChange(targets=(root.ref,),candidates=(topic,),explanation='Candidate'))]
        before=self.store.owned('demo','ChangeProposal')
        request=LearningRequest(request_id='rejected-final',context_ref=root.ref,subject_key='admin',text='Probe')

        response=service.request(request)

        self.assertEqual(response.kind,'FAILURE')
        self.assertEqual(response.proposal_refs,())
        self.assertEqual(response.application_status,'none')
        self.assertEqual(self.store.owned('demo','ChangeProposal'),before)
        self.assertEqual(self.store.owned('demo','TaskResult'),(failed_record,result_record))
        self.assertEqual(service.request(request),response)
        self.assertEqual(self.store.read_context('demo'),root)

    def test_admin_abandons_reopened_pending_request_without_replay(self):
        from smoke import prepare_demo
        service=prepare_demo(self.store,self.factory)
        root=self.store.read_context('demo')
        request=LearningRequest(request_id='orphan',context_ref=root.ref,subject_key='learner',text='Probe')
        self.store.claim_request(request.request_id,'demo',canonical(request.model_dump(mode='json')))
        with LearningStore(self.path) as reopened:
            resumed=LearningService(reopened,service.contract,service.policy,self.factory)
            with self.assertRaises(ValueError):
                resumed.abandon_request('demo','learner','orphan')
            terminal=resumed.abandon_request('demo','admin','orphan')
            self.assertEqual(terminal.kind,'FAILURE')
            self.assertEqual(resumed.request(request),terminal)
            self.assertEqual(resumed.request(request),terminal)
        self.factory.assert_not_called()

    def test_abandonment_wins_before_original_worker_commits(self):
        from smoke import prepare_demo
        task_ref=EntityRef.model_validate(ref('WorkerTask','late-task'))
        result_record=record('TaskResult','late-result',{'task':task_ref.model_dump(),
                                                      'status':'SUCCEEDED','content':'Synthetic'})
        engine=Mock(last_records=(result_record,),last_proposals=())
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        request=LearningRequest(request_id='in-flight',context_ref=root.ref,subject_key='learner',text='Probe')
        with LearningStore(self.path) as other:
            admin=LearningService(other,service.contract,service.policy,self.factory)
            engine.run.side_effect=lambda *args,**kwargs: (
                admin.abandon_request('demo','admin','in-flight'),
                LearningResponse(kind='ANSWER',content='Too late'))[1]
            response=service.request(request)
        self.assertEqual(response.kind,'FAILURE')
        self.assertEqual(self.store.owned('demo','TaskResult'),())
        self.factory.assert_not_called()

    def test_abandoned_request_replays_even_after_socratic_mode_changes(self):
        from smoke import prepare_demo
        engine=Mock(last_records=(),last_proposals=())
        engine.run.return_value=LearningResponse(kind='ANSWER',content='Which step would you try?')
        service=prepare_demo(self.store,lambda:engine)
        root=self.store.read_context('demo')
        old=LearningRequest(request_id='old',context_ref=root.ref,subject_key='learner',
                            text='Explain',problem_key='same')
        self.store.claim_request(old.request_id,'demo',canonical(old.model_dump(mode='json')))
        guide=old.model_copy(update={'request_id':'guide','intent':'SOCRATIC_GUIDANCE'})
        self.assertEqual(service.request(guide).kind,'ANSWER')
        terminal=service.abandon_request('demo','admin','old')

        self.assertEqual(service.request(old),terminal)
        self.assertEqual(engine.run.call_count,1)
