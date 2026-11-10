"""Course from an uploaded AIM-PRO model (S09a): upload, Curator job, review, project initialization.

An upload is checked (size, JSON, jjodel megamodel format, metamodels, scenario
and competency catalogue) and stored unchanged in the export directory that the
worker reads, under the SHA-256 of its bytes. A refused file leaves nothing
behind: no export, no job, no ALM record. Findings against the generated
contracts do not refuse a file; they come back as its diagnostics.
"""

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aimpro.audit import DEFAULT_PROJECT
from learning.contracts import Entity, EntityRef
from learning.store import LearningStore
from services.api_common.auth import CSRF_HEADER
from services.api_common.registry import ConfigurationError
from services.api_common.settings import ApiSettings
from services.authoring_api.app import create_app
from services.jobs.store import JobStore
from tests.authoring_cycle_fixtures import AUTH
from tests.seed import build_seed
from tests.services.course_fixtures import new_export_directory, write_course_template
from tests.services.oidc_fixtures import ISSUER, MAPPED_SUBJECT, NO_NETWORK, FakeProvider, auth_settings, write_identity_map
from tests.services.test_authoring_review_api import LEARNER_SUBJECT, ReviewApiCase
from tests.store_backends import block_network


COURSE = 'prompting-course'
LIMIT = 1024 * 1024
UPLOAD = '/contexts/{}/aimpro-exports'


class ExportsApiCase(ReviewApiCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = self.root / 'seed.sqlite'
        self.seed = build_seed(self.root / 'seed', self.location)
        self.policies = self.root / 'seed' / self.seed.policy_dir
        self.policy_file = self.policies / 'architecture-policy-1.json'
        self.exports = new_export_directory(self.root)
        self.jobs_location = self.root / 'jobs.sqlite'
        self.start_api()

    def start_api(self):
        self.provider = FakeProvider()
        identities = write_identity_map(self.root,
            {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'},
            {'issuer': ISSUER, 'subject': LEARNER_SUBJECT, 'subject_key': 'learner'})
        settings = ApiSettings(auth=auth_settings(), identity_map=identities, store=str(self.location),
                               policy_dir=self.policies, jobs_store=str(self.jobs_location),
                               aimpro_exports=self.exports, export_max_bytes=LIMIT,
                               course_template=write_course_template(self.root))
        self.app = create_app(settings, transport=self.provider.transport)
        self.staff = self.signed_in(MAPPED_SUBJECT)
        self.learner = self.signed_in(LEARNER_SUBJECT)

    def upload(self, content, context_id=AUTH, client=None, csrf=True, **params):
        client = client or self.staff
        headers = {'Content-Type': 'application/octet-stream'}
        if csrf:
            headers[CSRF_HEADER] = client.get('/auth/session').json()['csrf_token']
        return client.post(UPLOAD.format(context_id), content=content, headers=headers, params=params)

    def report(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def stored(self):
        """Every file of the export directory, hidden ones included, with its bytes."""
        return {path.name: path.read_bytes() for path in sorted(self.exports.iterdir())}

    def queued(self):
        """The job a worker would take next; ``None`` when nothing was queued."""
        with JobStore(self.jobs_location) as jobs:
            return jobs.claim()


class ExportUploadTest(ExportsApiCase):
    # Acceptance: the uploaded bytes are kept unchanged (digest test).
    def test_an_upload_is_stored_unchanged_under_the_digest_of_its_bytes(self):
        # Line ends and spacing that a parser would not keep: the stored file is the received one.
        content = DEFAULT_PROJECT.read_bytes().replace(b'\n', b'\r\n', 3) + b'\r\n\t \n'
        digest = hashlib.sha256(content).hexdigest()
        before = self.digests()
        report = self.report(self.upload(content))
        self.assertEqual(report['export'], {'name': digest + '.json', 'sha256': digest})
        self.assertEqual((report['size'], report['scenario'], report['competencies']),
                         (len(content), 'SCN01', 'elena_usecase_competencies'))
        self.assertEqual(self.stored(), {digest + '.json': content})
        self.assertEqual(hashlib.sha256((self.exports / (digest + '.json')).read_bytes()).hexdigest(), digest)
        # Uploading records nothing in the ALM store and queues nothing.
        self.assertEqual(self.digests(), before)
        self.assertIsNone(self.queued())

    def test_the_report_carries_the_diagnostics_of_the_model(self):
        report = self.report(self.upload(DEFAULT_PROJECT.read_bytes()))
        self.assertTrue(report['project_id'])
        self.assertTrue(report['root_id'])
        self.assertGreater(report['objects'], 0)
        # The reference export does not conform to the generated contracts: it is accepted with its findings.
        self.assertFalse(report['conforms'])
        self.assertTrue(report['contract_findings'])
        self.assertTrue(all({'code', 'object_id'} <= set(f) for f in report['contract_findings']))
        self.assertTrue(all({'code', 'object_id'} <= set(f) for f in report['source_diagnostics']))

    def test_the_same_upload_again_returns_the_same_export(self):
        content = DEFAULT_PROJECT.read_bytes()
        first = self.report(self.upload(content))
        stored = self.stored()
        self.assertEqual(self.report(self.upload(content)), first)
        self.assertEqual(self.stored(), stored)

    def test_a_file_under_the_export_name_with_other_bytes_is_never_replaced(self):
        content = DEFAULT_PROJECT.read_bytes()
        name = hashlib.sha256(content).hexdigest() + '.json'
        (self.exports / name).write_bytes(b'{"changed": true}')
        self.assertEqual(self.refused(self.upload(content), 409, 'conflict'),
                         'The export directory holds other bytes under this name')
        self.assertEqual(self.stored(), {name: b'{"changed": true}'})

    # Acceptance: an invalid file is refused with its reason; nothing is recorded.
    def test_an_invalid_file_is_refused_with_its_reason_and_nothing_is_recorded(self):
        project = DEFAULT_PROJECT.read_bytes()
        # The refusal names the models of the file, so the right scenario and catalogue can be entered.
        no_scenario = ('The scenario and the competency catalogue cannot be resolved in the export. Models in the export: '
                       'SCN01, assessment, elena_usecase_competencies, elena_usecase_scenario, learningphase, sustainability')
        cases = [
            (b'', {}, 'The file is empty'),
            (b' ' * (LIMIT + 1), {}, f'The file is larger than {LIMIT} bytes'),
            (b'\xff\xfe{}', {}, 'The file is not UTF-8 JSON'),
            (b'<xml/>', {}, 'The file is not UTF-8 JSON'),
            (b'[1, 2]', {}, 'The file is not a jjodel megamodel export, format 1.0'),
            (json.dumps({'format': 'jjodel-megamodel', 'formatVersion': '2.0'}).encode(), {},
             'The file is not a jjodel megamodel export, format 1.0'),
            (json.dumps({'format': 'jjodel-megamodel', 'formatVersion': '1.0'}).encode(), {},
             'The metamodels of the export cannot be read'),
            (project, {'scenario': 'NO-SUCH-SCENARIO'}, no_scenario),
            (project, {'competencies': 'no_such_catalogue'}, no_scenario),
        ]
        before = self.digests()
        for content, params, reason in cases:
            with self.subTest(reason=reason, params=params):
                self.assertEqual(self.refused(self.upload(content, **params), 422, 'validation'), reason)
        self.assertEqual(self.stored(), {})
        self.assertEqual(self.digests(), before)
        self.assertIsNone(self.queued())

    def test_uploading_needs_csrf_and_the_authority_to_propose(self):
        content = DEFAULT_PROJECT.read_bytes()
        self.refused(self.upload(content, csrf=False), 403, 'forbidden')
        self.refused(self.upload(content, client=self.learner), 403, 'forbidden')
        self.install_policy('admin', without_action='propose')
        self.refused(self.upload(content), 403, 'forbidden')
        self.refused(self.upload(content, context_id='no-such-context'), 404, 'context_unavailable')
        self.assertEqual(self.stored(), {})


class CourseFromModelTest(ExportsApiCase):
    """The whole S09a cycle through the API, with the dev-only synthetic worker of the browser tests."""

    def run_worker(self):
        from tests.synthetic_worker import main
        env = {'ALM_STORE': str(self.location), 'ALM_POLICY_DIR': str(self.policies),
               'ALM_JOBS_STORE': str(self.jobs_location), 'ALM_AIMPRO_EXPORTS': str(self.exports)}
        with patch.dict(os.environ, env):
            self.assertEqual(main(['--once']), 0)

    def pending(self, context_id):
        response = self.staff.get(f'/contexts/{context_id}/pending-proposals')
        self.assertEqual(response.status_code, 200, response.text)
        return [(Entity.model_validate(item['proposal']).ref, item['review_payload_key'])
                for item in response.json()['proposals']]

    def review_and_apply(self, proposal, operation_id):
        [(pending, key)] = self.pending(COURSE)
        self.assertEqual(pending, proposal)
        self.ok(self.decide(self.staff, COURSE, proposal, key))
        return self.ok(self.apply(self.staff, COURSE, proposal, operation_id))

    def context(self):
        response = self.staff.get(f'/contexts/{COURSE}')
        self.assertEqual(response.status_code, 200, response.text)
        return Entity.model_validate(response.json()['context'])

    def test_a_course_is_built_from_an_uploaded_model(self):
        self.assertEqual(self.post(self.staff, '/courses', {'context_id': COURSE}).status_code, 200)
        report = self.report(self.upload(DEFAULT_PROJECT.read_bytes(), COURSE))

        job = {'kind': 'generate-aimpro-syllabus', 'project': report['export'], 'source_scope': 'wp3',
               'query': 'prompting', 'scenario': report['scenario'], 'competencies': report['competencies']}
        queued = self.post(self.staff, f'/contexts/{COURSE}/jobs', {'request_id': 'curator-1', 'job': job})
        self.assertEqual(queued.status_code, 200, queued.text)
        self.run_worker()
        done = self.staff.get(f'/contexts/{COURSE}/jobs/curator-1').json()
        self.assertEqual(done['status'], 'PROPOSED', done)
        syllabus_proposal = EntityRef.model_validate(done['proposal_refs'][0])
        self.review_and_apply(syllabus_proposal, 'apply-syllabus')

        # The applied outline is the course's design; its approved syllabus is read through it.
        design = EntityRef.model_validate(self.context().fields['learningDesign'])
        approved = self.staff.get(f'/contexts/{COURSE}/designs/{design.id}/versions/{design.version}/syllabus')
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.headers['cache-control'], 'no-store')
        syllabus = EntityRef.model_validate(approved.json()['syllabus'])
        self.assertEqual(EntityRef.model_validate(approved.json()['proposal']).id, syllabus_proposal.id)

        command = {'request_id': 'init-1', 'project_id': 'prompting', 'syllabus': syllabus.model_dump(),
                   'base_context': self.context().ref.model_dump()}
        initialized = self.post(self.staff, f'/contexts/{COURSE}/projects', command)
        self.assertEqual(initialized.status_code, 200, initialized.text)
        self.assertEqual(initialized.headers['cache-control'], 'no-store')
        # The same request id and command replay the same proposal.
        self.assertEqual(self.post(self.staff, f'/contexts/{COURSE}/projects', command).json(), initialized.json())
        proposal = EntityRef.model_validate(initialized.json()['proposal'])
        self.review_and_apply(proposal, 'apply-project')

        inspection = self.staff.get(f'/contexts/{COURSE}/projects/prompting')
        self.assertEqual(inspection.status_code, 200, inspection.text)
        self.assertEqual(inspection.json()['project'], initialized.json()['project'])
        # The worker read the export as uploaded.
        self.assertEqual((self.exports / report['export']['name']).read_bytes(), DEFAULT_PROJECT.read_bytes())

    def test_initializing_needs_csrf_and_an_exact_current_base(self):
        self.assertEqual(self.post(self.staff, '/courses', {'context_id': COURSE}).status_code, 200)
        base = self.context().ref.model_dump()
        syllabus = {'type': 'Resource', 'id': 'no-such-syllabus', 'version': '1'}
        command = {'request_id': 'init-1', 'project_id': 'prompting', 'syllabus': syllabus, 'base_context': base}
        before = self.digests()
        self.refused(self.post(self.staff, f'/contexts/{COURSE}/projects', command, csrf=False), 403, 'forbidden')
        self.refused(self.post(self.learner, f'/contexts/{COURSE}/projects', command), 403, 'forbidden')
        self.refused(self.post(self.staff, f'/contexts/{COURSE}/projects', command), 422, 'validation')
        self.assertEqual(self.digests(), before)

    def test_a_design_that_is_not_the_current_outline_has_no_approved_syllabus(self):
        self.assertEqual(self.post(self.staff, '/courses', {'context_id': COURSE}).status_code, 200)
        response = self.staff.get(f'/contexts/{COURSE}/designs/no-such-design/versions/1/syllabus')
        self.refused(response, 422, 'validation')
        # A subject outside the course is refused before anything is read.
        response = self.learner.get(f'/contexts/{COURSE}/designs/no-such-design/versions/1/syllabus')
        self.refused(response, 403, 'forbidden')


class ExportSettingsTest(unittest.TestCase):
    def test_the_exports_module_needs_an_existing_export_directory(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            identities = write_identity_map(root, {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'})
            seed = build_seed(root / 'seed', root / 'seed.sqlite')
            values = dict(auth=auth_settings(), identity_map=identities, store=str(root / 'seed.sqlite'),
                          policy_dir=root / 'seed' / seed.policy_dir, jobs_store=str(root / 'jobs.sqlite'),
                          course_template=write_course_template(root))
            for exports in (None, root / 'missing'):
                with self.subTest(exports=exports), self.assertRaisesRegex(ConfigurationError, 'ALM_AIMPRO_EXPORTS'):
                    create_app(ApiSettings(**values, aimpro_exports=exports))


if __name__ == '__main__':
    unittest.main()
