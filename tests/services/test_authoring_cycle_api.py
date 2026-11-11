"""The rest of the authoring cycle through the API (S09c2): generator jobs, reviews and completion rules.

From a course whose project is initialized, the author queues the Evaluator, Teacher and Trainer jobs with
the exact refs of the project inspection, decides and applies each proposal, then proposes and applies the
completion rules. The project ends in the state of ``build_project()`` of ``tests/test_authoring_cycle.py``.
The worker runs in the test with synthetic models.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from learning.contracts import Entity, EntityRef
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore
from services.jobs.store import JobStore
from tests.authoring_cycle_fixtures import AUTH, ProductionAuthoring, trusted_policy
from tests.services.job_fixtures import SyntheticAgents, export_directory, worker
from tests.services.oidc_fixtures import NO_NETWORK
from tests.services.test_authoring_review_api import ReviewApiCase
from tests.store_backends import block_network
from tests.test_completion_rules import design_nodes


PROJECT = 'synthetic-course'
JOBS = (('generate-project-assessments', 'ASSESSMENT'), ('generate-project-teacher', 'TEACHER_CONTENT'),
        ('generate-project-trainer', 'TRAINER_CONTENT'))


def project_state(service):
    """What the cycle must reach: the selected artifact kinds, their receipts, stale dependencies, nodes without a rule."""
    view = service.inspect_authoring_project(AUTH, 'admin', PROJECT)
    snapshot = service._context(AUTH, 'admin').snapshot
    return {'kinds': [a.kind for a in view.manifest.artifacts],
            'receipts': [a.receipt is not None and a.approval_error is None for a in view.artifacts],
            'project_receipt': view.receipt is not None and view.approval_error is None,
            'stale': list(view.stale_dependencies),
            'without_rule': [n.id for n in design_nodes(snapshot, view.manifest.design) if not n.fields.get('completionRule')]}


def initialized(location):
    """A course whose Curator syllabus and project are applied: where the studio's generator forms start."""
    with LearningStore(location) as store:
        service = LearningService(store, load_contract(), trusted_policy(), Mock())
        service.bootstrap(AUTH, 'admin')
        ProductionAuthoring(service).curator()


def built(location):
    """The project state of ``build_project()``."""
    with LearningStore(location) as store:
        service = LearningService(store, load_contract(), trusted_policy(), Mock())
        service.bootstrap(AUTH, 'admin')
        author = ProductionAuthoring(service)
        author.curator()
        for kind in ('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'):
            author.review_and_apply(AUTH, author.generate(kind), 'approve-' + kind)
        author.configure_completion()
        return project_state(service)


class AuthoringCycleApiTest(ReviewApiCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = self.root / 'course.sqlite'
        initialized(self.location)
        self.policies = self.root / 'policies'
        self.policies.mkdir()
        self.policy_file = self.policies / 'architecture-policy-1.json'
        self.policy_file.write_text(trusted_policy().model_dump_json(indent=2), encoding='utf-8')
        self.agents = SyntheticAgents(export_directory(self.root))
        self.jobs = JobStore(self.root / 'jobs.sqlite')
        self.addCleanup(self.jobs.close)
        self.worker = worker(self.location, self.policies, self.jobs, self.agents, strict_events=True)
        self.start_api()

    def queue(self, request_id, job):
        return self.post(self.staff, f'/contexts/{AUTH}/jobs', {'request_id': request_id, 'job': job})

    def job(self, response, status):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], status)
        return response.json()

    def inspection(self):
        response = self.staff.get(f'/contexts/{AUTH}/projects/{PROJECT}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def base(self):
        return Entity.model_validate(self.staff.get(f'/contexts/{AUTH}').json()['context']).ref.model_dump()

    def review_and_apply(self, proposal, operation):
        pending = {Entity.model_validate(item['proposal']).ref: item['review_payload_key']
                   for item in self.staff.get(f'/contexts/{AUTH}/pending-proposals').json()['proposals']}
        self.ok(self.decide(self.staff, AUTH, proposal, pending[proposal]))
        self.ok(self.apply(self.staff, AUTH, proposal, operation))

    # Acceptance (S09c2): the cycle through the API reaches the project state of build_project().
    def test_the_generator_jobs_and_the_completion_rules_reach_the_state_of_build_project(self):
        for kind, artifact in JOBS:
            project = self.inspection()
            # The command a form sends: the exact project, base context and, after the Evaluator, its assessments.
            assessments = [a['resource'] for a in project['manifest']['artifacts'] if a['kind'] == 'ASSESSMENT']
            command = {'project': project['project'], 'base_context': self.base(), 'assessments': assessments}
            self.job(self.queue(kind, {'kind': kind, 'command': command}), 'QUEUED')
            self.worker.run_once()
            done = self.job(self.staff.get(f'/contexts/{AUTH}/jobs/{kind}'), 'PROPOSED')
            self.review_and_apply(EntityRef.model_validate(done['proposal_refs'][0]), 'apply-' + kind)
            self.assertIn(artifact, [a['kind'] for a in self.inspection()['manifest']['artifacts']])
        with LearningStore(self.location) as store:
            self.assertTrue(project_state(LearningService(store, load_contract(), trusted_policy(), Mock()))['without_rule'])

        command = {'request_id': 'completion', 'project': self.inspection()['project'], 'base_context': self.base()}
        response = self.post(self.staff, f'/contexts/{AUTH}/completion-rules', command)
        self.assertEqual(response.status_code, 200, response.text)
        proposed = response.json()
        self.assertEqual(sorted(proposed), ['design', 'domain', 'project', 'proposal'])
        # The same request id replays the same proposal.
        self.assertEqual(self.post(self.staff, f'/contexts/{AUTH}/completion-rules', command).json(), proposed)
        self.review_and_apply(EntityRef.model_validate(proposed['proposal']), 'apply-completion')

        with LearningStore(self.location) as store:
            state = project_state(LearningService(store, load_contract(), trusted_policy(), Mock()))
        self.assertEqual(state, built(self.root / 'reference.sqlite'))
        self.assertEqual(state['without_rule'], [])
        self.assertEqual(state['stale'], [])

    def test_completion_rules_on_a_stale_base_are_refused_and_need_content_authority(self):
        project = self.inspection()['project']
        command = {'request_id': 'completion', 'project': project, 'base_context': self.base()}
        # The project has no Trainer content yet.
        self.refused(self.post(self.staff, f'/contexts/{AUTH}/completion-rules', command), 422, 'validation')
        self.refused(self.post(self.learner, f'/contexts/{AUTH}/completion-rules', command), 403, 'forbidden')
        self.refused(self.post(self.staff, f'/contexts/{AUTH}/completion-rules', command, csrf=False), 403, 'forbidden')
        stale = {**command, 'request_id': 'stale', 'base_context': {**command['base_context'], 'version': 'old'}}
        self.refused(self.post(self.staff, f'/contexts/{AUTH}/completion-rules', stale), 409, 'conflict')


if __name__ == '__main__':
    unittest.main()
