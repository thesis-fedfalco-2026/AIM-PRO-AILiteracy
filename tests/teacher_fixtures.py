"""Explicit synthetic structured assets, never evidence of pedagogical validity."""

from aimpro.teacher_contracts import StructuredTeacherDraft


def structured_draft(data):
    citation = data.syllabus.artifact.draft.units[0].corpus_citations[0].model_dump(mode='json')
    common = {'title': 'Synthetic teaching asset', 'citations': [citation]}
    explanations, comparisons, peers, transcripts, units = [], [], [], [], []
    for unit in data.target_units:
        e, c, p, t = (unit.key + ':' + suffix for suffix in ('explanation', 'comparison', 'peer', 'transcript'))
        explanations.append(dict(common, key=e, content='State the business task, audience and tone explicitly.'))
        comparisons.append(dict(common, key=c, notice='Synthetic fictional case.',
            facts=[{'label': 'Customer', 'value': 'Morgan'}], weak_prompt='Draft a booking note.',
            improved_prompt='Draft a polite booking note to fictional customer Morgan.',
            worse_prompt='Draft an abrupt booking note to fictional customer Morgan.',
            commentary='The improved version specifies an audience and tone.'))
        peers.append(dict(common, key=p, notice='Synthetic fictional demonstration, not an assessment answer.',
            facts=[{'label': 'Customer', 'value': 'Morgan'}], introduction='I have a booking note to examine.',
            email_introduction='Here is the complete illustrative email.',
            prompt='Write a polite booking confirmation to fictional customer Morgan.',
            email={'subject': 'Fictional booking', 'salutation': 'Dear Morgan,',
                   'paragraphs': ['Your fictional booking is confirmed.', 'Please reply if your plans change.'],
                   'closing': 'Best wishes,', 'signature': 'Fictional booking team'},
            diagnosis='The task and audience are explicit; the polite closing supports the tone.'))
        transcripts.append(dict(common, key=t, parts=[
            {'kind': 'SPEECH', 'speaker': 'Teacher', 'text': 'I compare the specified audience and tone.'},
            {'kind': 'PROMPT', 'comparison_key': c, 'variant': 'IMPROVED'},
            {'kind': 'PEER_SCENE', 'peer_key': p}]))
        units.append({'key': unit.key, 'items': [{'key': 'explain', 'intent': 'EXPLAIN',
            'instruction': 'Read the explanation, comparison and complete peer demonstration.',
            'outcomes': unit.node.fields['outcomes'], 'material_keys': [e, c, p, t], 'citations': [citation]}]})
    return StructuredTeacherDraft(input_digest=data.digest, units=units, explanations=explanations,
        comparisons=comparisons, peers=peers, transcripts=transcripts,
        new_gaps=['Synthetic test assets have no pedagogical validation.'])
