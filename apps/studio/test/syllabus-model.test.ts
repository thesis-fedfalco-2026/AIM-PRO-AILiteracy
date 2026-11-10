import { describe, expect, it } from 'vitest';

import type { Entity } from '../src/features/review/reviewApi';
import {
  comparisonRows, editedDraft, isSyllabusProposal, newUnit, practiceName, unitInWords, withTarget,
} from '../src/features/review/syllabus';
import { EXCERPTS, FIRST, REVISED, TARGETS, draft, firstView, revisedView, unit } from './syllabus-fixture';

describe('syllabus in words', () => {
  it('names the target, competencies, practices and cited excerpts by their text', () => {
    expect(unitInWords(firstView(), FIRST.units[0]!)).toEqual({
      title: 'Prepare a fictional business prompt',
      purpose: 'Observe and practice stating a task, audience and tone.',
      intents: ['EXPLAIN', 'PRACTICE'],
      target: 'Construct a first prompt for a task from one’s own business.',
      competencies: ['AI Interaction & Prompting'],
      practices: [{ name: 'Modelling AI practices', text: 'The adviser builds a prompt live, thinking aloud.' }],
      citations: [{ claim: 'Specify task, audience and tone.', excerpts: [{ title: 'Synthetic prompting guide',
        text: 'State the task, the audience and the tone.', purpose: 'Task, audience and tone of a business prompt.',
        limitations: ['Synthetic excerpt.'] }] }],
      coverage: [],
    });
  });

  it('shows an id the texts do not name as it is', () => {
    const words = unitInWords(firstView(), unit('u', { source_target_id: 'other', source_practice_ids: ['p-x'],
      source_competency_ids: ['c-x'] }));
    expect([words.target, words.competencies, words.practices]).toEqual(['other', ['c-x'], [{ name: 'p-x', text: '' }]]);
  });

  it('reads practice class names as words', () => {
    expect(practiceName('ModellingAIPractices')).toBe('Modelling AI practices');
    expect(practiceName('PeerReview')).toBe('Peer review');
  });
});

describe('syllabus comparison', () => {
  it('lists each unit with its status and, for a changed unit, the fields that differ in words', () => {
    const rows = comparisonRows(revisedView(), revisedView().compared_with_refined!);
    expect(rows.map((row) => row.status)).toEqual(['CHANGED', 'ADDED']);
    expect(rows[0]!.fields).toEqual([{ field: 'purpose', before: ['Observe and practice stating a task, audience and tone.'],
      after: ['Observe a live prompt, then practice task, audience and tone.'] }]);
    expect(rows[1]!.before).toBeNull();
    expect(rows[1]!.after!.title).toBe('Explain two prompting choices');
    expect(rows[1]!.fields).toEqual([]);
  });

  it('shows competencies, practices and citations of a changed unit by their text', () => {
    const view = firstView();
    const after = unit('unit-0', { source_practice_ids: ['practice-2'] });
    const [row] = comparisonRows(view, { ...view.compared_with_current, units: [
      { status: 'CHANGED', target_id: 'target-1', before: FIRST.units[0]!, after,
        changed_fields: ['source_practice_ids', 'corpus_citations'] }] });
    expect(row!.fields).toEqual([
      { field: 'source_practice_ids', before: ['Modelling AI practices'], after: ['Peer review'] },
      { field: 'corpus_citations', before: ['Specify task, audience and tone. (Synthetic prompting guide)'],
        after: ['Specify task, audience and tone. (Synthetic prompting guide)'] }]);
  });
});

describe('syllabus proposal', () => {
  const proposal = (ids: string[]): Entity => ({ type: 'ChangeProposal', id: 'p', version: '1',
    provenance: { origin: 'GENERATED_PROPOSAL', responsible: 'admin', sources: [] },
    fields: { candidateDefinitions: ids.map((id) => ({ type: 'Resource', id, version: '1' })) } });

  it('is recognized by its syllabus record', () => {
    expect(isSyllabusProposal(proposal(['aimpro-syllabus-0a1b:syllabus', 'aimpro-syllabus-0a1b:source-snapshot']))).toBe(true);
    expect(isSyllabusProposal(proposal(['aimpro-syllabus-0a1b:source-snapshot', 'syllabus']))).toBe(false);
  });
});

describe('syllabus editor', () => {
  it('moves a unit to a target with its competencies and only the practices it allows', () => {
    const second = { ...TARGETS[0]!, id: 'target-2', competencies: [{ id: 'competency-2', name: 'Ethics', description: '' }],
      practices: [{ id: 'practice-3', name: 'CaseStudy', text: '' }] };
    const coverage = [{ requirement_key: 'r', planned_action: 'Explain' }];
    const moved = withTarget(unit('u', { coverage }), second);
    expect([moved.source_target_id, moved.source_competency_ids, moved.source_practice_ids, moved.coverage])
      .toEqual(['target-2', ['competency-2'], ['practice-3'], []]);
    const back = withTarget(unit('u', { source_practice_ids: ['practice-2'], coverage }), TARGETS[0]!);
    expect([back.source_practice_ids, back.coverage]).toEqual([['practice-2'], coverage]);
  });

  it('adds a unit with a new key on the first target, citing the first excerpt', () => {
    const added = newUnit(firstView(), draft('t', unit('unit-2'), unit('unit-0')));
    expect(added.key).toBe('unit-3');
    expect([added.source_target_id, added.source_competency_ids, added.source_practice_ids])
      .toEqual(['target-1', ['competency-1'], ['practice-1', 'practice-2']]);
    expect(added.corpus_citations).toEqual([{ resource_id: EXCERPTS[0]!.resource_id, resource_version: 'v1',
      document_ids: ['chunk-1'], supported_claim: '' }]);
  });

  it('sends the teacher text trimmed and drops empty gaps', () => {
    const edited = editedDraft({ ...REVISED, title: ' New title ', gaps: [' A gap ', '  '],
      units: [unit('u', { title: ' T ', purpose: ' P ' })] });
    expect([edited.title, edited.gaps, edited.units[0]!.title, edited.units[0]!.purpose])
      .toEqual(['New title', ['A gap'], 'T', 'P']);
  });
});
