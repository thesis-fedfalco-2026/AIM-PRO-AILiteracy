"""Deterministic Teacher rendering and field-scoped assessment compatibility checks."""

import re

from aimpro.lead import ReviewError
from aimpro.teacher_contracts import (PeerReference, PromptReference, Speech,
                                      StructuredTeacherDraft)
from learning.store import canonical


LABELS = ('PROMPT TEXT', 'PEER PROMPT', 'ILLUSTRATIVE EMAIL', 'PEER SCENE')
RESERVED = {*LABELS, *('END ' + label for label in LABELS)}


def _normalized(value):
    """Comparison only: do not alter the original or rendered value."""
    return ' '.join(value.split()).casefold()


def _assessments(data):
    from aimpro.generation_state import GeneratedArtifact
    for artifact in data.inputs:
        if artifact.selection.kind == 'ASSESSMENT':
            yield artifact, GeneratedArtifact.model_validate_json(
                artifact.resource.fields['contentOrLocator']).draft


def _stimuli(data):
    for artifact, draft in _assessments(data):
        for unit in draft.units:
            for item in unit.items:
                for stimulus in item.stimuli:
                    yield artifact.selection.resource, unit.key, stimulus


def validate_plan(data):
    plan = data.command.teacher_plan
    if data.role != 'TEACHER_CONTENT' or plan is None:
        raise ReviewError('Structured rendering requires an explicit Teacher plan')
    for artifact in data.inputs:
        review = artifact.approved_review
        if (review is None or review.artifact != artifact.selection.resource or
                review.decision != artifact.receipt.decision or
                review.reviewed_target.id != artifact.receipt.proposal.id or
                review.decision.type != 'HumanDecision' or
                review.reviewed_target.type != 'ChangeProposal' or not review.reason.strip()):
            raise ReviewError('Structured Teacher input lacks its exact host-resolved approval reason')
    stimuli = list(_stimuli(data))
    for anchor in plan.protected_case_facts:
        matches = [s for ref, unit, s in stimuli if ref == anchor.assessment and
                   unit == anchor.unit_key and s.key == anchor.stimulus_key]
        if len(matches) != 1 or anchor.quote not in matches[0].content:
            raise ReviewError('Protected case fact must quote an exact selected assessment stimulus')


def assessment_prompt_bodies(data):
    """Read actual approved prompt stimuli, never case-name mentions in commentary."""
    result = []
    for _, _, stimulus in _stimuli(data):
        if stimulus.kind != 'PROMPT_VARIANT':
            continue
        blocks = re.findall(r'^PROMPT TEXT\n(.*?)\nEND PROMPT TEXT(?:\n|$)',
                            stimulus.content, re.M | re.S)
        result.extend(blocks or [stimulus.content])
    return tuple(result)


def reused_prompt_bodies(data, prompts):
    protected = {_normalized(body) for body in assessment_prompt_bodies(data)}
    return tuple(prompt for prompt in prompts if _normalized(prompt) in protected)


def _literal(value):
    if any(line.strip() in RESERVED for line in value.splitlines()):
        raise ReviewError('Literal fields must not contain host protocol marker lines')
    return value


def _block(label, value):
    return label + '\n' + _literal(value) + '\nEND ' + label


def _facts(facts):
    labels = [_normalized(f.label) for f in facts]
    if len(labels) != len(set(labels)):
        raise ReviewError('Case fact labels must be unique')
    return '\n'.join(_literal(f.label) + ': ' + _literal(f.value) for f in facts)


def _email(email):
    fields = (email.subject, email.salutation, *email.paragraphs, email.closing, email.signature)
    for value in fields:
        _literal(value)
    if '\n' in email.subject or '\r' in email.subject:
        raise ReviewError('Email subject must be one line')
    return ('Subject: ' + email.subject + '\n\n' + email.salutation + '\n\n' +
            '\n\n'.join(email.paragraphs) + '\n\n' + email.closing + '\n' + email.signature)


def _peer_blocks(peer):
    return _block('PEER PROMPT', peer.prompt) + '\n\n' + _block('ILLUSTRATIVE EMAIL', _email(peer.email))


def _citations(*groups):
    found = {}
    for group in groups:
        for citation in group:
            found.setdefault(canonical(citation.model_dump(mode='json')), citation)
    return tuple(found.values())


def render_teacher(data, original):
    """Project a new wire draft, preserving it in full; never repair legacy output."""
    from aimpro.generators import Material, RenderedTeacherDraft, TeacherUnit
    validate_plan(data)
    if type(original) is not StructuredTeacherDraft:
        raise ReviewError('Expected the registered structured Teacher wire contract')
    original = StructuredTeacherDraft.model_validate(original.model_dump(mode='json'))
    if original.input_digest != data.digest:
        raise ReviewError('Structured Teacher output has a foreign input digest')
    materials = []
    keys = [v.key for group in (original.explanations, original.comparisons,
                               original.peers, original.transcripts) for v in group]
    if len(keys) != len(set(keys)):
        raise ReviewError('Structured Teacher material keys must be unique')
    comparisons = {v.key: v for v in original.comparisons}
    peers = {v.key: v for v in original.peers}
    transcript_keys = {v.key for v in original.transcripts}
    actual_links = set()
    case_values, prompts = [], []
    def material(value, kind, content, citations=None):
        materials.append(Material(key=value.key, kind=kind, title=value.title,
            content=content, citations=value.citations if citations is None else citations))
    for explanation in original.explanations:
        material(explanation, 'EXPLANATION', _literal(explanation.content))
    for comparison in original.comparisons:
        case_values.extend(f.value for f in comparison.facts)
        prompts.extend((comparison.weak_prompt, comparison.improved_prompt, comparison.worse_prompt))
        content = [_literal(comparison.notice), _facts(comparison.facts)]
        for name in ('weak', 'improved', 'worse'):
            content += [name.upper(), _block('PROMPT TEXT', getattr(comparison, name + '_prompt'))]
        content.append(_literal(comparison.commentary))
        material(comparison, 'EXAMPLE', '\n\n'.join(content))
    for peer in original.peers:
        case_values.extend(f.value for f in peer.facts)
        prompts.append(peer.prompt)
        material(peer, 'EXAMPLE', '\n\n'.join((_literal(peer.notice), _facts(peer.facts),
            _literal(peer.introduction), _literal(peer.email_introduction), _peer_blocks(peer), _literal(peer.diagnosis))))
    if reused_prompt_bodies(data, prompts):
        raise ReviewError('Structured Teacher reuses an actual selected assessment prompt body')
    protected = {_normalized(a.quote) for a in data.command.teacher_plan.protected_case_facts}
    if any(_normalized(value) in protected for value in case_values):
        raise ReviewError('An actual case fact reuses a protected selected assessment value')
    for transcript in original.transcripts:
        lines, citations, number = [], transcript.citations, 1
        for part in transcript.parts:
            if isinstance(part, Speech):
                lines.append(str(number) + '. ' + _literal(part.speaker) + ': ' + _literal(part.text))
                number += 1
            elif isinstance(part, PromptReference):
                value = comparisons.get(part.comparison_key)
                if value is None:
                    raise ReviewError('Transcript references a missing prompt comparison')
                lines.append(_block('PROMPT TEXT', getattr(value, part.variant.lower() + '_prompt')))
                citations = _citations(citations, value.citations)
            elif isinstance(part, PeerReference):
                peer = peers.get(part.peer_key)
                if peer is None:
                    raise ReviewError('Transcript references a missing peer example')
                actual_links.add((transcript.key, peer.key))
                lines += ['PEER SCENE', peer.notice, _facts(peer.facts),
                    str(number) + '. Peer owner: ' + _literal(peer.introduction),
                    _block('PEER PROMPT', peer.prompt),
                    str(number + 1) + '. Peer owner: ' + _literal(peer.email_introduction),
                    _block('ILLUSTRATIVE EMAIL', _email(peer.email)),
                    str(number + 2) + '. Peer owner: ' + _literal(peer.diagnosis), 'END PEER SCENE']
                citations = _citations(citations, peer.citations)
                number += 3
        material(transcript, 'TRANSCRIPT', '\n\n'.join(lines), citations)
    required = {(link.transcript_key, link.peer_key) for link in data.command.teacher_plan.transcript_peers}
    if (any(t not in transcript_keys or p not in peers for t, p in required) or
            not required <= actual_links or set(peers) != {p for _, p in actual_links}):
        raise ReviewError('Transcript omits a required complete peer scene')
    return RenderedTeacherDraft(input_digest=original.input_digest,
        units=tuple(TeacherUnit.model_validate(u.model_dump(mode='json')) for u in original.units),
        materials=tuple(materials), gaps=original.new_gaps, original=original,
        approved_review_notes=tuple(a.approved_review for a in data.inputs))
