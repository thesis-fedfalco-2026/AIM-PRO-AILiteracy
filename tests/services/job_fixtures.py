"""Synthetic agent jobs for the worker and API tests (S08).

The worker runs the production service methods; only the model and retrieval
responses are synthetic, as in ``tests/authoring_cycle_fixtures.py``. Nothing
here calls a model, a provider or the network.
"""

from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4

from aimpro.audit import DEFAULT_PROJECT
from aimpro.generators import GenerationCommand
from learning.store import LearningStore
from services.api_common.contexts import ContextServices, PolicyDirectory
from services.jobs.kinds import Resources
from services.jobs.worker import Worker
from tests.authoring_cycle_fixtures import AUTH
from tests.generator_fixtures import SyntheticModels
from tests.store_backends import _administer, backend, postgres_url
from tests.syllabus_fixtures import Curator, Reviewer
from tests.test_aimpro_retrieval import response as corpus_response


EXPORT = 'aimpro-export.json'
REQUIREMENT = 'Explain two prompting choices in a synthetic job.'


def new_jobs_location(case, directory):
    """A new jobs store of this test: a file, or the test database with its own jobs schema."""
    if backend(case) == 'sqlite':
        return Path(directory) / 'jobs.sqlite'
    schema = 'jobs_test_' + uuid4().hex
    patcher = patch('services.jobs.store.SCHEMA', schema)
    patcher.start()
    case.addCleanup(patcher.stop)
    case.addCleanup(_administer, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    return postgres_url()


def export_directory(directory):
    """A directory of AIM-PRO exports with an unchanged copy of the default project."""
    exports = Path(directory) / 'exports'
    exports.mkdir()
    shutil.copyfile(DEFAULT_PROJECT, exports / EXPORT)
    return exports


class SyntheticAgents:
    """What the worker holds in production, with synthetic responses; counts model construction."""

    def __init__(self, exports=None):
        self.models = SyntheticModels()
        self.curator, self.reviewer = Curator(), Reviewer()
        self.built = []
        self.searches = []
        self.exports = exports

    def authoring(self):
        self.built.append('authoring')
        dispatcher, lead, budget = self.models.factory()
        return _Combined(dispatcher, self.curator), _Lead(lead, self.reviewer), budget

    def search(self):
        self.built.append('search')

        def search(query, k, **kwargs):
            self.searches.append((query, k))
            return corpus_response()
        return search

    def resources(self):
        return Resources(authoring=self.authoring, search=self.search, exports=self.exports)


class _Combined:
    """One dispatcher for every authoring role, as ``build_aimpro_authoring`` returns."""

    def __init__(self, generators, curator):
        self.generators, self.curator = generators, curator

    def run(self, name, prompt, *args, **kwargs):
        from aimpro.syllabus import CURATOR
        if name == CURATOR:
            return self.curator.run(name, prompt)
        return self.generators.run(name, prompt, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.generators, name)


class _Lead:
    """The review Lead: syllabus verdicts for the Curator, generation verdicts otherwise."""

    def __init__(self, generators, syllabus):
        self.generators, self.syllabus = generators, syllabus

    def kickoff(self, prompt, response_format):
        from aimpro.syllabus import SyllabusVerdict
        if response_format is SyllabusVerdict:
            return self.syllabus.kickoff(prompt, response_format)
        return self.generators.kickoff(prompt, response_format)


def worker(store, policies, jobs, agents, **kwargs):
    return Worker(jobs, ContextServices(str(store), PolicyDirectory(policies)), agents.resources(), **kwargs)


def evaluator_command(store, project, requirements=(REQUIREMENT,)):
    """The Evaluator command of the seed's project on the current authoring context."""
    with LearningStore(store) as opened:
        base = opened.read_context(AUTH).ref
    return GenerationCommand(project=project, base_context=base, requirements=requirements)


def evaluator_job(command):
    return {'kind': 'generate-project-assessments', 'command': command.model_dump(mode='json')}
