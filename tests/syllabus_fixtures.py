"""Synthetic source-backed authoring fixtures; no live human decisions."""

from types import SimpleNamespace

from aimpro.didactic import CorpusCitation, targets
from aimpro.lead import prepare_input
from aimpro.retrieval import evidence_from_response
from aimpro.syllabus import SyllabusDraft, SyllabusUnit, SyllabusVerdict
from tests.test_aimpro_retrieval import response


def source():
    data = prepare_input()
    return data.model_copy(update={'corpus_evidence': evidence_from_response('prompting', 'wp3', 3, response())})


def syllabus(data=None):
    data = data or source()
    index = {o.id: o for o in data.source.objects}
    units = tuple(SyllabusUnit(key=f'unit-{i}', title='Prepare a fictional business prompt',
        source_target_id=target, source_competency_ids=tuple(index[target].references['competency']),
        source_practice_ids=tuple(sorted(practices)),
        purpose='Observe and practice stating a task, audience and tone with fictional data.',
        planned_intents=('EXPLAIN', 'PRACTICE'),
        corpus_citations=(CorpusCitation(resource_id='wp3:test', resource_version='v1',
            document_ids=('chunk-1',), supported_claim='Specify task, audience and tone in a business prompt.'),))
        for i, (target, practices) in enumerate(targets(data).items()))
    return SyllabusDraft(source_sha256=data.source.source_sha256,
        metamodel_fingerprint=data.metamodel_fingerprint, title='Synthetic business prompting syllabus',
        units=units, gaps=('Original source resource and vocabulary diagnostics remain unresolved.',))


def revised_syllabus(data=None):
    """A second syllabus on the same source (S09b): the first unit changed and a second unit on its target."""
    draft = syllabus(data)
    first = draft.units[0]
    return draft.model_copy(update={'title': 'Synthetic business prompting syllabus, revised', 'units': (
        first.model_copy(update={'purpose': 'Observe a live prompt, then practice task, audience and tone.'}),
        first.model_copy(update={'key': 'unit-explain', 'title': 'Explain two prompting choices',
                                 'purpose': 'Write a prompt for a fictional business and explain two choices.',
                                 'planned_intents': ('PRACTICE',)}))})


class Curator:
    """Returns ``value``, or ``revision`` when asked to revise a syllabus and one is set."""

    def __init__(self, value=None, revision=None):
        self.value = value or syllabus()
        self.revision = revision
        self.calls = []

    def run(self, name, prompt):
        self.calls.append((name, prompt))
        if self.revision is not None and 'AIMPRO_SYLLABUS_REVISION' in prompt.split('\nDATA\n')[0]:
            return self.revision
        return self.value


class Reviewer:
    def __init__(self):
        self.calls = []
        self.callback = None
        self.value = SyllabusVerdict(verdict='ACCEPT', source_alignment=True,
                                    citation_support=True, reason='Synthetic relevant source and aligned learning purposes.')

    def kickoff(self, prompt, response_format):
        self.calls.append((prompt, response_format))
        if self.callback:
            self.callback()
        return SimpleNamespace(pydantic=self.value)
