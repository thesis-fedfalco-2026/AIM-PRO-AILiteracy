"""Read-only Authoring API (S05): parity with the CLI on the same seeded database.

Each endpoint is compared with the CLI command that reads the same records,
for the same subject and the same trusted policy. The identity provider is in
memory and the network is blocked except for the PostgreSQL test service.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from learning.__main__ import main as cli_main
from learning.authoring import ProjectManifest
from learning.contracts import Entity, Finding
from learning.decisions import proposal_candidates
from learning.projects import ProjectInspection
from learning.releases import ReleaseInspection
from learning.store import LearningStore
from aimpro.syllabus_state import ApprovedSyllabus
from services.api_common.settings import ApiSettings
from services.authoring_api.app import create_app
from tests.authoring_cycle_fixtures import AUTH, DELIVERY, DELIVERY_TWO
from tests.seed import build_seed
from tests.services.oidc_fixtures import (ISSUER, MAPPED_SUBJECT, NO_NETWORK, FakeProvider,
                                          auth_settings, log_in, write_identity_map)
from tests.store_backends import block_network, new_store_location, on_both_backends


LEARNER_SUBJECT = 'kc-user-learner'
UNAVAILABLE = {'error': 'context_unavailable', 'detail': 'Context unavailable'}


def resource_path(context_id, ref, view):
    return f'/contexts/{context_id}/resources/{quote(ref.id, safe="")}/versions/{quote(ref.version, safe="")}/{view}'


def entities(items):
    return [Entity.model_validate(item) for item in items]


@on_both_backends
class AuthoringReadApiTest(unittest.TestCase):
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
        self.provider = FakeProvider()
        identities = write_identity_map(self.root,
            {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'},
            {'issuer': ISSUER, 'subject': LEARNER_SUBJECT, 'subject_key': 'learner'})
        settings = ApiSettings(auth=auth_settings(), identity_map=identities,
                               store=str(self.location), policy_dir=self.policies)
        self.app = create_app(settings, transport=self.provider.transport)
        self.staff = self.signed_in(MAPPED_SUBJECT)
        self.learner = self.signed_in(LEARNER_SUBJECT)

    def signed_in(self, subject):
        client = TestClient(self.app, base_url='https://testserver', raise_server_exceptions=False,
                            follow_redirects=False)
        self.assertEqual(log_in(client, self.provider, subject).status_code, 303)
        return client

    def cli(self, subject, context_id, *args, policy=None, answer=None):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors), patch('builtins.input', return_value=answer or ''):
            status = cli_main(['--db', str(self.location), '--policy', str(policy or self.policy_file),
                               '--subject', subject, '--context', context_id, *args])
        text = output.getvalue()
        return status, json.JSONDecoder().raw_decode(text)[0] if text.startswith('{') else None

    def get(self, client, path):
        response = client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def digests(self):
        with LearningStore(self.location) as store:
            return store.table_digests()

    def endpoints(self, context_id):
        return [f'/contexts/{context_id}', f'/contexts/{context_id}/pending-proposals',
                f'/contexts/{context_id}/projects/{self.seed.project_id}',
                resource_path(context_id, self.seed.project, 'project-syllabus'),
                resource_path(context_id, self.seed.release, 'release')]

    def test_context_summary_matches_cli_show(self):
        status, shown = self.cli('admin', AUTH, 'show')
        self.assertEqual(status, 0)
        summary = self.get(self.staff, f'/contexts/{AUTH}')
        self.assertEqual(set(summary), {'context', 'entities', 'findings'})
        self.assertEqual(Entity.model_validate(summary['context']), Entity.model_validate(shown['context']))
        self.assertEqual(entities(summary['entities']), entities(shown['entities']))
        self.assertEqual([Finding.model_validate(f) for f in summary['findings']],
                         [Finding.model_validate(f) for f in shown['findings']])
        self.assertIn('ChangeProposal', {e['type'] for e in summary['entities']})

    def test_a_learner_only_subject_gets_the_show_redaction(self):
        status, shown = self.cli('learner', DELIVERY_TWO, 'show')
        self.assertEqual(status, 0)
        summary = self.get(self.learner, f'/contexts/{DELIVERY_TWO}')
        self.assertEqual(entities(summary['entities']), entities(shown['entities']))
        self.assertEqual(Entity.model_validate(summary['context']), Entity.model_validate(shown['context']))
        self.assertEqual({e['type'] for e in summary['entities']}, {'ExecutionContext', 'Participant'})
        self.assertEqual([e['fields']['subjectKey'] for e in summary['entities'] if e['type'] == 'Participant'],
                         ['learner'])
        staff = self.get(self.staff, f'/contexts/{DELIVERY_TWO}')
        self.assertTrue({'PolicySet', 'ChangeProposal'} <= {e['type'] for e in staff['entities']})
        self.assertEqual(self.get(self.learner, f'/contexts/{DELIVERY_TWO}/pending-proposals'), {'proposals': []})
        self.assertEqual(len(self.get(self.staff, f'/contexts/{DELIVERY_TWO}/pending-proposals')['proposals']), 1)

    def test_pending_proposals_match_cli_show_and_the_decide_preview(self):
        for context_id in (AUTH, DELIVERY_TWO):
            with self.subTest(context_id):
                pending = self.get(self.staff, f'/contexts/{context_id}/pending-proposals')['proposals']
                _, shown = self.cli('admin', context_id, 'show')
                awaiting = [e for e in entities(shown['entities'])
                            if e.type == 'ChangeProposal' and e.fields['status'] == 'AWAITING_DECISION']
                self.assertEqual(sorted(Entity.model_validate(p['proposal']).ref.id for p in pending),
                                 sorted(e.id for e in awaiting))
                self.assertEqual([Entity.model_validate(p['proposal']).ref for p in pending],
                                 list(self.seed.pending_proposals[context_id]))
                for item in pending:
                    proposal = Entity.model_validate(item['proposal'])
                    status, preview = self.cli('admin', context_id, 'decide', proposal.ref.model_dump_json(),
                                               'APPROVE', '--reason', 'Parity preview only', answer='no')
                    self.assertEqual(status, 1)
                    self.assertEqual(Entity.model_validate(preview['target']), proposal)
                    self.assertEqual(entities(item['candidates']), entities(preview['candidates']))
                    self.assertEqual(item['review_payload_key'], preview['target']['fields']['reviewPayloadKey'])

    def test_project_inspection_matches_cli(self):
        status, shown = self.cli('admin', AUTH, 'show-authoring-project', self.seed.project_id)
        self.assertEqual(status, 0)
        inspection = self.get(self.staff, f'/contexts/{AUTH}/projects/{self.seed.project_id}')
        self.assertEqual(ProjectInspection.model_validate(inspection), ProjectInspection.model_validate(shown))
        self.assertEqual(ProjectInspection.model_validate(inspection).project, self.seed.project)
        self.assertIsInstance(ProjectInspection.model_validate(inspection).manifest, ProjectManifest)

    def test_approved_project_syllabus_matches_cli(self):
        status, shown = self.cli('admin', AUTH, 'show-project-syllabus', self.seed.project.model_dump_json())
        self.assertEqual(status, 0)
        syllabus = self.get(self.staff, resource_path(AUTH, self.seed.project, 'project-syllabus'))
        self.assertEqual(ApprovedSyllabus.model_validate(syllabus), ApprovedSyllabus.model_validate(shown))

    def test_release_inspection_matches_cli_show_release(self):
        status, shown = self.cli('admin', AUTH, 'show-release', self.seed.release.model_dump_json())
        self.assertEqual(status, 0)
        release = self.get(self.staff, resource_path(AUTH, self.seed.release, 'release'))
        self.assertEqual(ReleaseInspection.model_validate(release), ReleaseInspection.model_validate(shown))
        self.assertEqual(ReleaseInspection.model_validate(release).findings, ())

    def test_a_context_whose_policy_file_is_not_installed_is_unavailable(self):
        for path in self.endpoints(DELIVERY):
            with self.subTest(path):
                response = self.staff.get(path)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual({k: response.json()[k] for k in UNAVAILABLE}, UNAVAILABLE)
        missing = self.staff.get('/contexts/no-such-context')
        self.assertEqual(missing.status_code, 404)
        self.assertEqual({k: missing.json()[k] for k in UNAVAILABLE}, UNAVAILABLE)
        self.assertEqual(self.cli('admin', DELIVERY, 'show')[0], 2)
        # Installing the approved preview is the operator action that makes it available.
        preview = self.output / self.seed.delivery_policy_preview
        shutil.copy(preview, self.policies / preview.name)
        status, shown = self.cli('admin', DELIVERY, 'show', policy=preview)
        self.assertEqual(status, 0)
        summary = self.get(self.staff, f'/contexts/{DELIVERY}')
        self.assertEqual(entities(summary['entities']), entities(shown['entities']))
        self.assertEqual(summary['context']['fields']['policies'], self.seed.delivery_policy.model_dump())

    def test_refusals_match_the_cli(self):
        with LearningStore(self.location) as store:
            older = next(c.ref for p in store.owned(AUTH, 'ChangeProposal') if p.fields['status'] == 'APPLIED'
                         for c in proposal_candidates(store, p)
                         if c.type == 'Resource' and c.id == self.seed.project.id and c.ref != self.seed.project)
        cases = [
            (self.learner, f'/contexts/{AUTH}', 403, ('learner', AUTH, 'show')),
            (self.learner, f'/contexts/{DELIVERY_TWO}/projects/{self.seed.project_id}', 403,
             ('learner', DELIVERY_TWO, 'show-authoring-project', self.seed.project_id)),
            (self.staff, f'/contexts/{AUTH}/projects/unknown-project', 422,
             ('admin', AUTH, 'show-authoring-project', 'unknown-project')),
            (self.staff, resource_path(AUTH, older, 'project-syllabus'), 409,
             ('admin', AUTH, 'show-project-syllabus', older.model_dump_json())),
            (self.staff, resource_path(AUTH, self.seed.project, 'release'), 422,
             ('admin', AUTH, 'show-release', self.seed.project.model_dump_json())),
        ]
        for client, path, expected, command in cases:
            with self.subTest(path):
                response = client.get(path)
                self.assertEqual(response.status_code, expected, response.text)
                self.assertEqual(set(response.json()), {'error', 'detail', 'request_id'})
                self.assertEqual(self.cli(*command)[0], 2)

    def test_reads_require_a_session(self):
        anonymous = TestClient(self.app, base_url='https://testserver', raise_server_exceptions=False)
        for path in self.endpoints(AUTH):
            with self.subTest(path):
                response = anonymous.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()['error'], 'unauthenticated')

    def test_endpoints_never_write(self):
        before = self.digests()
        for client in (self.staff, self.learner):
            for context_id in (AUTH, DELIVERY, DELIVERY_TWO, 'no-such-context'):
                for path in self.endpoints(context_id):
                    client.get(path)
        TestClient(self.app, base_url='https://testserver').get(f'/contexts/{AUTH}')
        self.assertEqual(self.digests(), before)


if __name__ == '__main__':
    unittest.main()
