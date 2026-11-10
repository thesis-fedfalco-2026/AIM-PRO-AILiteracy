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


def verdict(**changes):
    """The synthetic reviewer's acceptance, or a verdict with ``changes``."""
    return SyllabusVerdict(verdict='ACCEPT', source_alignment=True, citation_support=True,
                           reason='Synthetic relevant source and aligned learning purposes.').model_copy(update=changes)


# A rejection whose reason must never reach an error message, a log line or an event.
REJECTION = verdict(verdict='REJECT', citation_support=False,
                    reason='Synthetic reviewer text: the cited excerpt does not support the unit claim.')


class Curator:
    """Returns ``value``; ``revision`` when asked to revise and ``retry`` when asked to try again, if set."""

    def __init__(self, value=None, revision=None, retry=None):
        self.value = value or syllabus()
        self.revision, self.retry = revision, retry
        self.calls = []

    def run(self, name, prompt):
        self.calls.append((name, prompt))
        instructions = prompt.split('\nDATA\n')[0]
        if self.retry is not None and 'AIMPRO_SYLLABUS_RETRY' in instructions:
            return self.retry
        if self.revision is not None and 'AIMPRO_SYLLABUS_REVISION' in instructions:
            return self.revision
        return self.value


# A teacher's reason holding this text makes the synthetic reviewer reject each review prompt once (dev only).
REJECT_ONCE = '[synthetic reviewer: reject the first draft]'


class Reviewer:
    """Returns the ``first`` verdicts in order, then ``value``: ``Reviewer(REJECTION)`` rejects once, then accepts.

    A review prompt holding :data:`REJECT_ONCE` (in the reasons of a revision) is rejected the first time it is
    seen, so the synthetic worker and the browser tests can show a rejected attempt followed by an accepted one.
    """

    def __init__(self, *first):
        self.calls = []
        self.callback = None
        self.queue = list(first)
        self.value = verdict()

    def kickoff(self, prompt, response_format):
        self.calls.append((prompt, response_format))
        if self.callback:
            self.callback()
        if REJECT_ONCE in prompt and [p for p, _ in self.calls].count(prompt) == 1:
            return SimpleNamespace(pydantic=REJECTION)
        return SimpleNamespace(pydantic=self.queue.pop(0) if self.queue else self.value)
