"""Review endpoints (S06): decide and apply through the API with the guarantees of the CLI.

A decision carries the review payload key the reviewer was shown; a key or a
revision that is no longer current is refused with 409 before anything is
written. An application carries an operation id; a replay returns the same
change. Both are writes, so both need the session's CSRF token. The CLI and the
API work on the same database and continue each other's work.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from learning.__main__ import main as cli_main
from learning.contracts import Entity, EntityRef
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore, canonical
from services.api_common.auth import CSRF_HEADER
from services.api_common.settings import ApiSettings
from services.authoring_api.app import create_app
from tests.authoring_cycle_fixtures import AUTH, DELIVERY, DELIVERY_TWO
from tests.learning_fixtures import record, ref
from tests.seed import build_seed
from tests.services.course_fixtures import module_settings
from tests.services.oidc_fixtures import (ISSUER, MAPPED_SUBJECT, NO_NETWORK, FakeProvider,
                                          auth_settings, log_in, write_identity_map)
from tests.store_backends import block_network, new_store_location, on_both_backends
from tests.test_learning_assessment import assessment_bundle
from tests.test_learning_context import policy as session_policy


LEARNER_SUBJECT = 'kc-user-learner'
REASON = 'Synthetic review of the exact payload'
ERROR_FIELDS = {'error', 'detail', 'request_id'}


class ReviewApiCase(unittest.TestCase):
    """An API app on ``self.location`` with ``self.policies``, and the CLI on the same files."""

    def start_api(self):
        self.provider = FakeProvider()
        identities = write_identity_map(self.root,
            {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'},
            {'issuer': ISSUER, 'subject': LEARNER_SUBJECT, 'subject_key': 'learner'})
        settings = ApiSettings(auth=auth_settings(), identity_map=identities, store=str(self.location),
                               policy_dir=self.policies, jobs_store=str(self.root / 'jobs.sqlite'), **module_settings(self.root))
        self.app = create_app(settings, transport=self.provider.transport)
        self.staff = self.signed_in(MAPPED_SUBJECT)
        self.learner = self.signed_in(LEARNER_SUBJECT)

    def signed_in(self, subject):
        client = TestClient(self.app, base_url='https://testserver', raise_server_exceptions=False,
                            follow_redirects=False)
        self.assertEqual(log_in(client, self.provider, subject).status_code, 303)
        return client

    def cli(self, subject, context_id, *args, answer='CONFIRM'):
        """Run the CLI; ``answer`` is the reply to the ``CONFIRM`` prompt, or a function of the prompt."""
        output, errors = StringIO(), StringIO()
        reply = {'side_effect': answer} if callable(answer) else {'return_value': answer}
        with redirect_stdout(output), redirect_stderr(errors), patch('builtins.input', **reply):
            status = cli_main(['--db', str(self.location), '--policy', str(self.policy_file),
                               '--subject', subject, '--context', context_id, *args])
        text = output.getvalue()
        # ``decide`` prints the reviewed payload before the result; the result is the last JSON document.
        documents, decoder, index = [], json.JSONDecoder(), 0
        while (start := text.find('{', index)) != -1:
            document, index = decoder.raw_decode(text, start)
            documents.append(document)
        return status, documents[-1] if documents else None

    def post(self, client, path, body, csrf=True):
        headers = {CSRF_HEADER: client.get('/auth/session').json()['csrf_token']} if csrf else {}
        return client.post(path, json=body, headers=headers)

    def decide(self, client, context_id, target, key, decision='APPROVE', reason=REASON):
        return self.post(client, f'/contexts/{context_id}/decisions', {
            'target': target.model_dump(), 'decision': decision, 'reason': reason, 'review_payload_key': key})

    def apply(self, client, context_id, proposal, operation_id):
        return self.post(client, f'/contexts/{context_id}/applications',
                         {'proposal': proposal.model_dump(), 'operation_id': operation_id})

    def ok(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return Entity.model_validate(response.json())

    def refused(self, response, status, error):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(set(response.json()), ERROR_FIELDS)
        self.assertEqual(response.json()['error'], error)
        return response.json()['detail']

    def digests(self):
        with LearningStore(self.location) as store:
            return store.table_digests()

    def install_policy(self, subject, *, roles=None, without_action=None):
        """Change one subject's grant in the installed trusted policy; the API reads it on the next request."""
        data = json.loads(self.policy_file.read_text(encoding='utf-8'))
        grant = data['subjects'][subject]
        if roles is not None:
            grant['roles'] = roles
        if without_action is not None:
            grant['actions'] = {context: [a for a in actions if a != without_action]
                                for context, actions in grant['actions'].items()}
        self.policy_file.write_text(json.dumps(data), encoding='utf-8')


@on_both_backends
class AuthoringReviewApiTest(ReviewApiCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = new_store_location(self, temp.name, 'seed.sqlite')
        self.output = self.root / 'seed'
        self.seed = build_seed(self.output, self.location)
        self.policies = self.output / self.seed.policy_dir
        self.policy_file = self.policies / 'architecture-policy-1.json'
        self.start_api()

    def pending(self, context_id):
        response = self.staff.get(f'/contexts/{context_id}/pending-proposals')
        self.assertEqual(response.status_code, 200, response.text)
        return [(Entity.model_validate(item['proposal']).ref, item['review_payload_key'])
                for item in response.json()['proposals']]

    def applied_proposal(self, context_id, other_than):
        with LearningStore(self.location) as store:
            return next(p.ref for p in store.owned(context_id, 'ChangeProposal')
                        if p.fields['status'] == 'APPLIED' and p.id != other_than.id)

    # S09c2 part 2 (issue #121): one proposal with its candidates, whatever its status.
    def test_every_proposal_is_read_with_its_candidates_whatever_its_status(self):
        with LearningStore(self.location) as store:
            proposals = {p.id: p for p in store.owned(AUTH, 'ChangeProposal')}
            expected = {p.id: (p, [c.model_dump(mode='json') for c in proposal_candidates(store, p)])
                        for p in proposals.values()}
        self.assertGreater(len({p.fields['status'] for p, _ in expected.values()}), 1)
        pending = dict((ref.id, key) for ref, key in self.pending(AUTH))
        for proposal_id, (proposal, candidates) in expected.items():
            with self.subTest(status=proposal.fields['status']):
                response = self.staff.get(f'/contexts/{AUTH}/proposals/{proposal_id}')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                body = response.json()
                self.assertEqual(Entity.model_validate(body['proposal']), proposal)
                self.assertEqual(body['candidates'], candidates)
                if proposal_id in pending:
                    self.assertEqual(body['review_payload_key'], pending[proposal_id])
        self.refused(self.staff.get(f'/contexts/{AUTH}/proposals/no-such-proposal'), 404, 'not_found')
        # A subject that may not see the pending proposals reads no proposal either.
        pending_status = self.learner.get(f'/contexts/{AUTH}/pending-proposals').status_code
        self.assertEqual(self.learner.get(f'/contexts/{AUTH}/proposals/{next(iter(expected))}').status_code,
                         pending_status)
        self.assertNotEqual(pending_status, 200)

    def test_a_decision_on_the_key_the_reviewer_saw_is_recorded(self):
        [(proposal, key)] = self.pending(AUTH)
        decision = self.ok(self.decide(self.staff, AUTH, proposal, key))
        self.assertEqual(decision.type, 'HumanDecision')
        self.assertEqual((decision.fields['target'], decision.fields['decision'], decision.fields['reviewedPayloadKey']),
                         (proposal.model_dump(), 'APPROVE', key))
        self.assertEqual(decision.provenance.responsible, 'admin')
        self.assertEqual(self.pending(AUTH), [])
        status, shown = self.cli('admin', AUTH, 'show')
        self.assertEqual(status, 0)
        self.assertIn(decision, [Entity.model_validate(e) for e in shown['entities']])

    def test_a_stale_key_is_refused_with_409_and_records_nothing(self):
        [(proposal, key)] = self.pending(AUTH)
        [(_, other_key)] = self.pending(DELIVERY_TWO)
        before = self.digests()
        for stale in (other_key, key[:-1] + ('0' if key[-1] != '0' else '1')):
            with self.subTest(stale=stale):
                self.refused(self.decide(self.staff, AUTH, proposal, stale), 409, 'conflict')
        self.assertEqual(self.digests(), before)

    def test_a_proposal_decided_after_loading_is_refused_with_409_until_reloaded(self):
        [(proposal, key)] = self.pending(AUTH)
        # Another reviewer decides with the CLI after this reviewer loaded the inbox.
        self.assertEqual(self.cli('admin', AUTH, 'decide', proposal.model_dump_json(), 'REJECT',
                                  '--reason', 'Another reviewer decided first')[0], 0)
        before = self.digests()
        self.refused(self.decide(self.staff, AUTH, proposal, key), 409, 'conflict')
        self.assertEqual(self.digests(), before)
        # Reloading shows the current revision; the decision on it is a revocation.
        current = next(Entity.model_validate(e) for e in self.staff.get(f'/contexts/{AUTH}').json()['entities']
                       if e['type'] == 'ChangeProposal' and e['id'] == proposal.id)
        self.assertEqual(current.fields['status'], 'REJECTED')
        decision = self.ok(self.decide(self.staff, AUTH, current.ref, current.fields['reviewPayloadKey']))
        self.assertEqual(decision.fields['target'], current.ref.model_dump())

    def test_the_cli_records_nothing_if_another_reviewer_decides_before_confirm(self):
        [(proposal, key)] = self.pending(AUTH)
        recorded = []
        def another_reviewer_then_confirm(prompt):
            recorded.append(self.ok(self.decide(self.staff, AUTH, proposal, key, decision='REJECT')))
            return 'CONFIRM'
        status, _ = self.cli('admin', AUTH, 'decide', proposal.model_dump_json(), 'APPROVE', '--reason', REASON,
                             answer=another_reviewer_then_confirm)
        self.assertEqual(status, 2)
        self.assertEqual(len(recorded), 1)
        _, shown = self.cli('admin', AUTH, 'show')
        decisions = [e for e in shown['entities'] if e['type'] == 'HumanDecision'
                     and e['fields']['target']['id'] == proposal.id]
        self.assertEqual([Entity.model_validate(e) for e in decisions], recorded)

    def test_the_cli_decides_only_the_current_revision_as_the_api(self):
        [(proposal, key)] = self.pending(AUTH)
        self.ok(self.decide(self.staff, AUTH, proposal, key))
        before = self.digests()
        self.assertEqual(self.cli('admin', AUTH, 'decide', proposal.model_dump_json(), 'REJECT', '--reason', REASON)[0], 2)
        self.assertEqual(self.digests(), before)
        current = next(Entity.model_validate(e) for e in self.staff.get(f'/contexts/{AUTH}').json()['entities']
                       if e['type'] == 'ChangeProposal' and e['id'] == proposal.id)
        status, revocation = self.cli('admin', AUTH, 'decide', current.ref.model_dump_json(), 'REJECT', '--reason', REASON)
        self.assertEqual((status, revocation['fields']['target']), (0, current.ref.model_dump()))

    def test_a_cli_decision_is_applied_through_the_api_and_replayed_by_the_cli(self):
        [(proposal, _)] = self.pending(AUTH)
        status, decision = self.cli('admin', AUTH, 'decide', proposal.model_dump_json(), 'APPROVE', '--reason', REASON)
        self.assertEqual((status, decision['type']), (0, 'HumanDecision'))
        change = self.ok(self.apply(self.staff, AUTH, proposal, 'apply-evaluator-2'))
        # The cause is the proposal's current revision, the one the decision moved to APPROVED.
        self.assertEqual((change.type, change.fields['cause']['id']), ('StateChange', proposal.id))
        before = self.digests()
        status, replayed = self.cli('admin', AUTH, 'apply', proposal.model_dump_json(), '--operation-id', 'apply-evaluator-2')
        self.assertEqual(status, 0)
        self.assertEqual(Entity.model_validate(replayed), change)
        self.assertEqual(self.ok(self.apply(self.staff, AUTH, proposal, 'apply-evaluator-2')), change)
        self.assertEqual(self.digests(), before)

    def test_an_api_decision_is_applied_by_the_cli_and_replayed_through_the_api(self):
        [(proposal, key)] = self.pending(AUTH)
        decision = self.ok(self.decide(self.staff, AUTH, proposal, key))
        status, change = self.cli('admin', AUTH, 'apply', proposal.model_dump_json(), '--operation-id', 'apply-evaluator-2')
        self.assertEqual(status, 0)
        change = Entity.model_validate(change)
        self.assertEqual((change.type, change.fields['authorizationBasis']),
                         ('StateChange', canonical(decision.ref.model_dump())))
        before = self.digests()
        self.assertEqual(self.ok(self.apply(self.staff, AUTH, proposal, 'apply-evaluator-2')), change)
        self.assertEqual(self.digests(), before)

    def test_application_requires_an_operation_id_and_an_approved_proposal(self):
        [(proposal, key)] = self.pending(AUTH)
        path = f'/contexts/{AUTH}/applications'
        for body in ({'proposal': proposal.model_dump()}, {'proposal': proposal.model_dump(), 'operation_id': ' '}):
            with self.subTest(body=body):
                self.refused(self.post(self.staff, path, body), 422, 'validation')
        before = self.digests()
        self.assertEqual(self.refused(self.apply(self.staff, AUTH, proposal, 'too-early'), 422, 'validation'),
                         'Proposal is not approved')
        self.assertEqual(self.cli('admin', AUTH, 'apply', proposal.model_dump_json(), '--operation-id', 'too-early')[0], 2)
        self.assertEqual(self.digests(), before)
        self.ok(self.decide(self.staff, AUTH, proposal, key))
        change = self.ok(self.apply(self.staff, AUTH, proposal, 'apply-evaluator-2'))
        # The operation id names one application: reusing it for another proposal is a conflict.
        before = self.digests()
        self.refused(self.apply(self.staff, AUTH, self.applied_proposal(AUTH, proposal), 'apply-evaluator-2'), 409, 'conflict')
        self.assertEqual(self.digests(), before)
        self.assertEqual(self.ok(self.apply(self.staff, AUTH, proposal, 'apply-evaluator-2')), change)

    def test_reviewer_role_checks_are_unchanged(self):
        [(evaluator, evaluator_key)] = self.pending(AUTH)
        [(delivery_import, import_key)] = self.pending(DELIVERY_TWO)
        cases = [
            ('content authority', {'roles': ['ASSESSOR']}, AUTH, evaluator, evaluator_key,
             422, 'validation', 'Content authority is required'),
            ('administrative authority', {'roles': ['CONTENT_RESPONSIBLE', 'ASSESSOR']}, DELIVERY_TWO,
             delivery_import, import_key, 422, 'validation', 'Administrative authority is required'),
            ('no decide grant', {'without_action': 'decide'}, AUTH, evaluator, evaluator_key,
             403, 'forbidden', 'Action is not authorized'),
        ]
        original = self.policy_file.read_text(encoding='utf-8')
        before = self.digests()
        for name, grant, context_id, proposal, key, status, error, detail in cases:
            with self.subTest(name):
                self.install_policy('admin', **grant)
                self.assertEqual(self.refused(self.decide(self.staff, context_id, proposal, key), status, error), detail)
                self.assertEqual(self.cli('admin', context_id, 'decide', proposal.model_dump_json(), 'APPROVE',
                                          '--reason', REASON)[0], 2)
                self.policy_file.write_text(original, encoding='utf-8')
        self.refused(self.decide(self.learner, DELIVERY_TWO, delivery_import, import_key), 403, 'forbidden')
        self.assertEqual(self.cli('learner', DELIVERY_TWO, 'decide', delivery_import.model_dump_json(), 'APPROVE',
                                  '--reason', REASON)[0], 2)
        self.assertEqual(self.digests(), before)
        # Administrative authority alone covers every kind, as in the CLI.
        self.install_policy('admin', roles=['ADMINISTRATOR'])
        self.ok(self.decide(self.staff, DELIVERY_TWO, delivery_import, import_key))

    def test_both_endpoints_require_the_csrf_token(self):
        [(proposal, key)] = self.pending(AUTH)
        decision = {'target': proposal.model_dump(), 'decision': 'APPROVE', 'reason': REASON, 'review_payload_key': key}
        application = {'proposal': self.applied_proposal(AUTH, proposal).model_dump(), 'operation_id': 'csrf'}
        other_token = self.learner.get('/auth/session').json()['csrf_token']
        anonymous = TestClient(self.app, base_url='https://testserver', raise_server_exceptions=False)
        before = self.digests()
        for path, body in ((f'/contexts/{AUTH}/decisions', decision), (f'/contexts/{AUTH}/applications', application)):
            for headers in ({}, {CSRF_HEADER: ''}, {CSRF_HEADER: 'wrong-token'}, {CSRF_HEADER: other_token}):
                with self.subTest(path=path, headers=headers):
                    self.assertEqual(self.refused(self.staff.post(path, json=body, headers=headers), 403, 'forbidden'),
                                     'CSRF token missing or invalid')
            with self.subTest(path=path, client='anonymous'):
                self.refused(anonymous.post(path, json=body), 401, 'unauthenticated')
        self.assertEqual(self.digests(), before)

    def test_writes_on_an_unavailable_context_answer_404(self):
        [(proposal, key)] = self.pending(DELIVERY_TWO)
        before = self.digests()
        for context_id in (DELIVERY, 'no-such-context'):
            with self.subTest(context_id):
                self.refused(self.decide(self.staff, context_id, proposal, key), 404, 'context_unavailable')
                self.refused(self.apply(self.staff, context_id, proposal, 'unavailable'), 404, 'context_unavailable')
        self.assertEqual(self.digests(), before)


@on_both_backends
class AssessmentAuthorityApiTest(ReviewApiCase):
    """An Evaluator verdict needs assessment authority, through the API as through the CLI."""

    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = new_store_location(self, temp.name, 'session.sqlite')
        self.policies = self.root / 'policies'
        self.policies.mkdir()
        self.policy_file = self.policies / 'policy-1.json'
        self.policy_file.write_text(session_policy().model_dump_json(), encoding='utf-8')
        with LearningStore(self.location) as store:
            store.seed(assessment_bundle(), owner='session')
            service = LearningService(store, load_contract(), session_policy(), Mock())
            evidence = service.submit('session', 'learner', EntityRef.model_validate(ref('ActivityDefinition', 'activity')),
                                      '4', 'attempt')
            evaluation = record('Evaluation', 'evaluation', {'context': evidence.fields['context'],
                'evidence': [evidence.ref.model_dump()], 'specification': ref('AssessmentSpecification', 'assessment'),
                'mode': 'FORMATIVE', 'result': 'Correct answer', 'reviewPayloadKey': 'pending'})
            proposal = service.propose('session', 'admin', (store.read_context('session').ref,), (evaluation,),
                                       'Confirm the synthetic performance')
        self.proposal, self.key = proposal.ref, proposal.fields['reviewPayloadKey']
        self.start_api()

    def test_an_evaluation_needs_assessment_authority(self):
        before = self.digests()
        self.install_policy('admin', roles=['CONTENT_RESPONSIBLE'])
        self.assertEqual(self.refused(self.decide(self.staff, 'session', self.proposal, self.key), 422, 'validation'),
                         'Assessment authority is required')
        self.assertEqual(self.cli('admin', 'session', 'decide', self.proposal.model_dump_json(), 'APPROVE',
                                  '--reason', REASON)[0], 2)
        self.assertEqual(self.digests(), before)
        self.install_policy('admin', roles=['ASSESSOR'])
        decision = self.ok(self.decide(self.staff, 'session', self.proposal, self.key))
        self.assertEqual(decision.fields['reviewedPayloadKey'], self.key)


if __name__ == '__main__':
    unittest.main()
