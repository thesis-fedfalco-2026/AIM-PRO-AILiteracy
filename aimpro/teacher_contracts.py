"""Structured Teacher wire data; authority and rendering remain host controlled."""

from typing import Annotated, ClassVar, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aimpro.didactic import CorpusCitation
from learning.contracts import EntityRef, Record, Text


Verbatim = Annotated[str, StringConstraints(strict=True, min_length=1)]


class Part(Record):
    @field_validator('*')
    @classmethod
    def nonblank(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError('Teacher text must not be blank')
        return value


class TranscriptPeerLink(Record):
    transcript_key: Text
    peer_key: Text


class ProtectedCaseFact(Record):
    assessment: EntityRef
    unit_key: Text
    stimulus_key: Text
    quote: Verbatim

    @model_validator(mode='after')
    def exact(self):
        if self.assessment.type != 'Resource' or self.assessment.version.lower() == 'latest':
            raise ValueError('Protected facts require an exact assessment Resource')
        if not self.quote.strip():
            raise ValueError('Protected case quote must not be blank')
        return self


class TeacherPlan(Record):
    format_version: Literal[1] = 1
    transcript_peers: tuple[TranscriptPeerLink, ...] = ()
    protected_case_facts: tuple[ProtectedCaseFact, ...] = ()

    @model_validator(mode='after')
    def unique(self):
        for values in (self.transcript_peers, self.protected_case_facts):
            if len(set(values)) != len(values):
                raise ValueError('Teacher plan links and protected facts must be unique')
        return self


class ApprovedReview(Part):
    """Exact historical approval evidence, never learner text or new consent."""
    artifact: EntityRef
    decision: EntityRef
    reviewed_target: EntityRef
    reviewed_payload_key: Text
    reason: Verbatim


class CaseFact(Part):
    label: Text
    value: Verbatim


class ProseMaterial(Part):
    key: Text
    title: Text
    content: Verbatim
    citations: tuple[CorpusCitation, ...] = Field(min_length=1)


class PromptComparison(Part):
    key: Text
    title: Text
    notice: Verbatim
    facts: tuple[CaseFact, ...] = Field(min_length=1, max_length=32)
    weak_prompt: Verbatim
    improved_prompt: Verbatim
    worse_prompt: Verbatim
    commentary: Verbatim
    citations: tuple[CorpusCitation, ...] = Field(min_length=1)


class IllustrativeEmail(Part):
    subject: Verbatim
    salutation: Verbatim
    paragraphs: tuple[Verbatim, ...] = Field(min_length=1, max_length=64)
    closing: Verbatim
    signature: Verbatim

    @field_validator('paragraphs')
    @classmethod
    def nonblank_paragraphs(cls, value):
        if any(not text.strip() for text in value):
            raise ValueError('Email paragraphs must not be blank')
        return value


class PeerExample(Part):
    key: Text
    title: Text
    notice: Verbatim
    facts: tuple[CaseFact, ...] = Field(min_length=1, max_length=32)
    introduction: Verbatim
    email_introduction: Verbatim
    prompt: Verbatim
    email: IllustrativeEmail
    diagnosis: Verbatim
    citations: tuple[CorpusCitation, ...] = Field(min_length=1)


class Speech(Part):
    kind: Literal['SPEECH'] = 'SPEECH'
    speaker: Text
    text: Verbatim


class PromptReference(Record):
    kind: Literal['PROMPT'] = 'PROMPT'
    comparison_key: Text
    variant: Literal['WEAK', 'IMPROVED', 'WORSE']


class PeerReference(Record):
    kind: Literal['PEER_SCENE'] = 'PEER_SCENE'
    peer_key: Text


TranscriptPart = Annotated[Speech | PromptReference | PeerReference, Field(discriminator='kind')]


class TeachingTranscript(Part):
    key: Text
    title: Text
    parts: tuple[TranscriptPart, ...] = Field(min_length=1, max_length=128)
    citations: tuple[CorpusCitation, ...] = Field(min_length=1)


class StructuredTeacherItem(Part):
    key: Text
    intent: Literal['EXPLAIN']
    instruction: Verbatim
    outcomes: tuple[EntityRef, ...] = Field(min_length=1)
    material_keys: tuple[Text, ...] = Field(min_length=1)
    citations: tuple[CorpusCitation, ...] = Field(min_length=1)


class StructuredTeacherUnit(Record):
    key: Text
    items: tuple[StructuredTeacherItem, ...] = Field(min_length=1, max_length=24)


class StructuredTeacherDraft(Record):
    # Provider grammar compilers reject this contract's combined size (probes, 6 November 2026).
    # The prompt carries the schema; the host validates the returned text unchanged.
    prompt_json_schema: ClassVar[bool] = True

    kind: Literal['STRUCTURED_TEACHER_DRAFT'] = 'STRUCTURED_TEACHER_DRAFT'
    input_digest: Text
    units: tuple[StructuredTeacherUnit, ...] = Field(min_length=1, max_length=24)
    explanations: tuple[ProseMaterial, ...] = Field(min_length=1, max_length=24)
    comparisons: tuple[PromptComparison, ...] = Field(max_length=24)
    peers: tuple[PeerExample, ...] = Field(max_length=24)
    transcripts: tuple[TeachingTranscript, ...] = Field(min_length=1, max_length=24)
    new_gaps: tuple[Verbatim, ...] = ()

    @field_validator('new_gaps')
    @classmethod
    def nonblank_gaps(cls, value):
        if any(not text.strip() for text in value):
            raise ValueError('New gaps must not be blank')
        return value
