import type { SyllabusProposalView } from '../src/features/review/reviewApi';

/** Synthetic syllabus proposals and their view, as `GET …/syllabus-proposals/{id}` returns it (S09b). */
const citation = (claim: string) =>
  ({ resource_id: 'wp3:test', resource_version: 'v1', document_ids: ['chunk-1'], supported_claim: claim });

export const unit = (key: string, fields: Record<string, unknown> = {}) => ({
  key, title: 'Prepare a fictional business prompt', source_target_id: 'target-1',
  source_competency_ids: ['competency-1'], source_practice_ids: ['practice-1'],
  purpose: 'Observe and practice stating a task, audience and tone.', planned_intents: ['EXPLAIN', 'PRACTICE'],
  corpus_citations: [citation('Specify task, audience and tone.')], coverage: [], ...fields,
}) as SyllabusProposalView['syllabus']['draft']['units'][number];

export const draft = (title: string, ...units: ReturnType<typeof unit>[]) =>
  ({ kind: 'SYLLABUS_DRAFT', source_sha256: 'sha', metamodel_fingerprint: 'fp', title, units, gaps: ['No rubric yet.'] }) as
    SyllabusProposalView['syllabus']['draft'];

const ref = (id: string, version = '1') => ({ type: 'ChangeProposal', id, version });

export const record = (id: string, syllabus: SyllabusProposalView['syllabus']['draft'], fields: Record<string, unknown> = {}) => ({
  proposal: ref(id), status: 'AWAITING_DECISION', responsible: 'admin', draft: syllabus, reviewed_by_agent: true,
  review: { verdict: 'ACCEPT', source_alignment: true, citation_support: true, reason: 'Aligned with the source.' },
  edited_by: null, revision_reasons: [], ...fields,
}) as SyllabusProposalView['syllabus'];

export const FIRST = draft('Business prompting', unit('unit-0'));
export const REVISED = draft('Business prompting, revised',
  unit('unit-0', { purpose: 'Observe a live prompt, then practice task, audience and tone.' }),
  unit('unit-explain', { title: 'Explain two prompting choices', planned_intents: ['PRACTICE'],
    purpose: 'Write a prompt and explain two choices.' }));

const comparison = (units: unknown[], fields: Record<string, unknown> = {}) =>
  ({ title_changed: false, gaps_added: [], gaps_removed: [], order_changed: false, units, ...fields }) as
    SyllabusProposalView['compared_with_current'];

export const TARGETS: SyllabusProposalView['targets'] = [{
  id: 'target-1', statement: 'Construct a first prompt for a task from one’s own business.',
  competencies: [{ id: 'competency-1', name: 'AI Interaction & Prompting', description: 'Interact with AI systems.' }],
  practices: [
    { id: 'practice-1', name: 'ModellingAIPractices', text: 'The adviser builds a prompt live, thinking aloud.' },
    { id: 'practice-2', name: 'PeerReview', text: 'Pairs compare their prompts.' }],
}];

export const EXCERPTS: SyllabusProposalView['excerpts'] = [{
  resource_id: 'wp3:test', resource_version: 'v1', document_id: 'chunk-1', title: 'Synthetic prompting guide',
  uri: 'https://example.org/guide', licence: 'CC-BY-4.0', text: 'State the task, the audience and the tone.',
  purpose: 'Task, audience and tone of a business prompt.', limitations: ['Synthetic excerpt.'],
}];

/** The first Curator proposal, on a course without a syllabus. */
export const firstView = (): SyllabusProposalView => ({
  syllabus: record('p-syllabus', FIRST), targets: TARGETS, excerpts: EXCERPTS, refined: null,
  compared_with_refined: null, course_design: 'NONE', current: null,
  compared_with_current: comparison([{ status: 'ADDED', target_id: 'target-1', before: null, after: FIRST.units[0],
    changed_fields: [] }]),
});

/** The Curator's revision of the first proposal, which the teacher sent back with a reason. */
export const revisedView = (): SyllabusProposalView => ({
  syllabus: record('p-revised', REVISED, { revision_reasons: ['Add a unit where participants explain their choices.'] }),
  targets: TARGETS, excerpts: EXCERPTS,
  refined: record('p-syllabus', FIRST, { status: 'DRAFT' }),
  compared_with_refined: comparison([
    { status: 'CHANGED', target_id: 'target-1', before: FIRST.units[0], after: REVISED.units[0], changed_fields: ['purpose'] },
    { status: 'ADDED', target_id: 'target-1', before: null, after: REVISED.units[1], changed_fields: [] },
  ], { title_changed: true }),
  course_design: 'NONE', current: null,
  compared_with_current: comparison(REVISED.units.map((after) =>
    ({ status: 'ADDED', target_id: 'target-1', before: null, after, changed_fields: [] }))),
});
