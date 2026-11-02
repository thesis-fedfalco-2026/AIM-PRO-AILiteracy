from types import SimpleNamespace

from aimpro.didactic import Criterion, DidacticDraft, DidacticVerdict, DraftActivity, DraftUnit, Level
from aimpro.lead import prepare_input


def draft(data=None):
    data = data or prepare_input()
    return DidacticDraft(source_sha256=data.source.source_sha256,
        metamodel_fingerprint=data.metamodel_fingerprint, title='First business prompt workshop',
        units=(DraftUnit(source_target_id='Pointer1792169221668_USER_96', title='Watch, annotate and draft',
            activities=(DraftActivity(source_practice_ids=('Pointer1792169384659_USER_127',),
                title='Observe a prompt revision', intent='EXPLAIN',
                instruction='Compare weak and improved payment-reminder prompts using fictional customer details.',
                material='Synthetic draft: compare “Write a reminder” with “Draft a polite reminder to fictional customer Alex about invoice EXAMPLE-01”. Discuss the added task and context.'),
                DraftActivity(source_practice_ids=('Pointer1792169384659_USER_127',),
                    title='Write and explain your first prompt', intent='PRACTICE',
                    instruction='Write one prompt for a business task with fictional details and explain two choices.',
                    material='Synthetic draft worksheet: task, fictional audience, context, constraints, two explanations.',
                    criteria=(Criterion(key='clarity', description='The prompt makes its business task clear.',
                        levels=(Level(key='unclear', description='The task cannot be identified.'),
                                Level(key='clear', description='The task and fictional audience can be identified.'))),)))),))


class TeachingLead:
    def __init__(self, data=None, *, verdict='ACCEPT', value=None, callback=None):
        self.value = value or draft(data)
        self.verdict = verdict
        self.calls = []
        self.callback = callback

    def kickoff(self, prompt, response_format):
        self.calls.append((prompt, response_format))
        if self.callback:
            self.callback()
            self.callback = None
        value = self.value if response_format is DidacticDraft else DidacticVerdict(
            verdict=self.verdict, reason='Synthetic review fixture; resources remain unresolved.')
        return SimpleNamespace(pydantic=value)
