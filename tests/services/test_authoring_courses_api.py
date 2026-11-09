"""Course creation from the studio (S09a): the API writes the new course's trusted policy.

An operator installs a course template that names who may create courses and
the source scopes a new course receives. ``POST /courses`` writes one new policy
file in ``ALM_POLICY_DIR`` that grants the creator administration of that
context only, and bootstraps the context in PREPARATION/DRAFT. It never changes
an installed policy file; the same request again returns the same course.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from learning.contracts import EntityRef
from learning.policies import TrustedPolicy
from learning.service import LearningService
from learning.store import LearningStore
from services.api_common.registry import ConfigurationError
from services.api_common.settings import ApiSettings
from services.authoring_api.app import create_app
from tests.authoring_cycle_fixtures import AUTH, DELIVERY_TWO
from tests.seed import build_seed
from tests.services.course_fixtures import new_export_directory, write_course_template
from tests.services.oidc_fixtures import ISSUER, MAPPED_SUBJECT, NO_NETWORK, FakeProvider, auth_settings, write_identity_map
from tests.services.test_authoring_review_api import LEARNER_SUBJECT, ReviewApiCase
from tests.store_backends import block_network, new_store_location, on_both_backends


COURSE = 'prompting-course'
ACTIONS = ['read', 'bootstrap', 'propose', 'decide', 'apply', 'interact']


@on_both_backends
class CoursesApiTest(ReviewApiCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = new_store_location(self, temp.name, 'seed.sqlite')
        self.seed = build_seed(self.root / 'seed', self.location)
        self.policies = self.root / 'seed' / self.seed.policy_dir
        self.policy_file = self.policies / 'architecture-policy-1.json'
        self.template = write_course_template(self.root)
        self.start_api()

    def start_api(self):
        self.provider = FakeProvider()
        identities = write_identity_map(self.root,
            {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'},
            {'issuer': ISSUER, 'subject': LEARNER_SUBJECT, 'subject_key': 'learner'})
        settings = ApiSettings(auth=auth_settings(), identity_map=identities, store=str(self.location),
                               policy_dir=self.policies, jobs_store=str(self.root / 'jobs.sqlite'),
                               aimpro_exports=new_export_directory(self.root), course_template=self.template)
        self.app = create_app(settings, transport=self.provider.transport)
        self.staff = self.signed_in(MAPPED_SUBJECT)
        self.learner = self.signed_in(LEARNER_SUBJECT)

    def create(self, context_id=COURSE, client=None, csrf=True):
        return self.post(client or self.staff, '/courses', {'context_id': context_id}, csrf=csrf)

    def created(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def files(self):
        """Every installed policy file with the digest of its bytes."""
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(self.policies.iterdir())}

    def test_a_course_gets_its_own_new_policy_and_a_preparation_draft_context(self):
        before = self.files()
        body = self.created(self.create())
        policy_ref = EntityRef(type='PolicySet', id='course:' + COURSE, version='1')
        self.assertEqual(body, {'context_id': COURSE, 'policy_ref': policy_ref.model_dump()})

        # One new file; every installed file keeps its exact bytes.
        written = self.policies / f'course-{COURSE}-1.json'
        self.assertEqual(self.files(), {**before, written.name: self.files()[written.name]})
        policy = TrustedPolicy.model_validate_json(written.read_bytes())
        self.assertEqual(policy.model_dump(mode='json'), {
            'policy_ref': policy_ref.model_dump(),
            'subjects': {'admin': {'roles': ['ADMINISTRATOR', 'CONTENT_RESPONSIBLE'], 'actions': {COURSE: ACTIONS}}},
            'scopes': {'wp3': {'contexts': [COURSE], 'subjects': ['admin'], 'activities': [], 'resources': [],
                               'sources': ['wp3'], 'operations': ['read']}},
            'rule_bindings': []})

        with LearningStore(self.location) as store:
            root = store.read_context(COURSE)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        self.assertEqual(root.fields['policies'], {'type': 'PolicySet', 'id': 'course:' + COURSE, 'version': '1'})
        # The new context is served at once, with its new policy; the creator is its only participant.
        summary = self.staff.get(f'/contexts/{COURSE}')
        self.assertEqual(summary.status_code, 200, summary.text)
        participants = [e for e in summary.json()['entities'] if e['type'] == 'Participant']
        self.assertEqual([p['fields']['subjectKey'] for p in participants], ['admin'])
        self.assertEqual(self.learner.get(f'/contexts/{COURSE}').status_code, 403)

    def test_the_same_request_again_returns_the_same_course(self):
        first = self.created(self.create())
        files = self.files()
        with LearningStore(self.location) as store:
            digests = store.table_digests()
        self.assertEqual(self.created(self.create()), first)
        self.assertEqual(self.files(), files)
        with LearningStore(self.location) as store:
            self.assertEqual(store.table_digests(), digests)

    def test_an_interrupted_creation_is_completed_by_the_same_request(self):
        # The policy file is written, then the bootstrap does not happen (the API stops).
        with patch.object(LearningService, 'bootstrap', side_effect=RuntimeError('stopped')):
            self.refused(self.create(), 500, 'internal')
        self.assertIn(f'course-{COURSE}-1.json', self.files())
        with LearningStore(self.location) as store:
            self.assertFalse(store.has_context(COURSE))
        files = self.files()
        self.assertEqual(self.created(self.create())['context_id'], COURSE)
        self.assertEqual(self.files(), files)
        with LearningStore(self.location) as store:
            self.assertTrue(store.has_context(COURSE))

    def test_only_a_creator_of_the_template_may_create_a_course(self):
        before = self.files()
        self.refused(self.create(client=self.learner), 403, 'forbidden')
        self.refused(self.create(csrf=False), 403, 'forbidden')
        write_course_template(self.root, creators=('someone-else',))
        self.refused(self.create(), 403, 'forbidden')
        self.assertEqual(self.files(), before)
        with LearningStore(self.location) as store:
            self.assertFalse(store.has_context(COURSE))

    def test_an_existing_context_is_never_taken_over(self):
        before = self.files()
        for context_id in (AUTH, DELIVERY_TWO):
            with self.subTest(context_id):
                self.assertEqual(self.refused(self.create(context_id), 409, 'conflict'),
                                 'A course or a policy already uses this id')
        self.assertEqual(self.files(), before)

    def test_an_id_named_by_an_installed_policy_is_refused(self):
        data = json.loads(self.policy_file.read_text(encoding='utf-8'))
        data['policy_ref']['id'] = 'operator-policy'
        data['subjects']['admin']['actions'] = {COURSE: ['read']}
        data['scopes'] = {}
        (self.policies / 'operator-policy.json').write_text(json.dumps(data), encoding='utf-8')
        before = self.files()
        self.assertEqual(self.refused(self.create(), 409, 'conflict'), 'A course or a policy already uses this id')
        self.assertEqual(self.files(), before)

    def test_a_different_file_under_the_course_policy_name_is_never_replaced(self):
        # A valid policy of the operator that does not name the course, under the name the API would write.
        data = json.loads(self.policy_file.read_text(encoding='utf-8'))
        data['policy_ref']['id'] = 'operator-copy'
        (self.policies / f'course-{COURSE}-1.json').write_text(json.dumps(data), encoding='utf-8')
        before = self.files()
        self.assertEqual(self.refused(self.create(), 409, 'conflict'),
                         'A different policy file is installed under this name')
        self.assertEqual(self.files(), before)
        with LearningStore(self.location) as store:
            self.assertFalse(store.has_context(COURSE))

    def test_a_course_id_is_a_short_lowercase_name(self):
        before = self.files()
        for context_id in ('', 'Upper', '-leading', 'trailing-', 'dot.ted', '../escape', 'a' * 65, 'with space'):
            with self.subTest(context_id):
                self.refused(self.create(context_id), 422, 'validation')
        self.assertEqual(self.files(), before)


class CourseSettingsTest(unittest.TestCase):
    def settings(self, root, **values):
        identities = write_identity_map(root, {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'})
        seed = build_seed(root / 'seed', root / 'seed.sqlite')
        defaults = dict(store=str(root / 'seed.sqlite'), policy_dir=root / 'seed' / seed.policy_dir,
                        jobs_store=str(root / 'jobs.sqlite'), aimpro_exports=new_export_directory(root),
                        course_template=write_course_template(root))
        return ApiSettings(auth=auth_settings(), identity_map=identities, **{**defaults, **values})

    def test_the_courses_module_needs_a_valid_course_template(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            settings = self.settings(root)
            invalid = root / 'invalid.json'
            invalid.write_text('{"format": 1, "creators": []}', encoding='utf-8')
            for template in (None, invalid, root / 'missing.json'):
                with self.subTest(template=template), self.assertRaisesRegex(ConfigurationError, 'ALM_COURSE_TEMPLATE'):
                    create_app(settings.model_copy(update={'course_template': template}))

    def test_a_deployment_without_the_courses_module_needs_no_template(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            create_app(self.settings(root, course_template=None, modules=('contexts',)))

    def test_settings_come_from_the_environment(self):
        env = {'ALM_OIDC_ISSUER': ISSUER, 'ALM_OIDC_CLIENT_ID': 'c', 'ALM_OIDC_CLIENT_SECRET': 's',
               'ALM_OIDC_REDIRECT_URI': 'https://api.test/auth/callback', 'ALM_IDENTITY_MAP': 'map.json',
               'ALM_COURSE_TEMPLATE': 'template.json', 'ALM_AIMPRO_EXPORTS': 'exports',
               'ALM_API_EXPORT_MAX_BYTES': '2048'}
        settings = ApiSettings.from_env(env)
        self.assertEqual((settings.course_template, settings.aimpro_exports, settings.export_max_bytes),
                         (Path('template.json'), Path('exports'), 2048))
        defaults = ApiSettings.from_env({k: v for k, v in env.items() if not k.startswith(('ALM_COURSE', 'ALM_AIMPRO', 'ALM_API_EXPORT'))})
        self.assertEqual((defaults.course_template, defaults.aimpro_exports, defaults.export_max_bytes),
                         (None, None, 10 * 1024 * 1024))


if __name__ == '__main__':
    unittest.main()
