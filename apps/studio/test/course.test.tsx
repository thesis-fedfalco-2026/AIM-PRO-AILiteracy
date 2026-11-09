import { cleanup, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import en from '../src/i18n/en.json';
import type { Reply } from './harness';
import { renderStudio, SESSION } from './harness';

const provenance = { origin: 'GENERATED_PROPOSAL', responsible: 'admin', sources: [] };
const entity = (type: string, id: string, fields: Record<string, unknown>) => ({ type, id, version: 'v1', fields, provenance });
const ref = (type: string, id: string) => ({ type, id, version: 'v1' });

const CONTEXT = entity('ExecutionContext', 'ctx', { learningDesign: ref('LearningDesign', 'design-1'), status: 'DRAFT', mode: 'AUTHORING' });
const ENTITIES = [
  CONTEXT,
  entity('LearningDesign', 'design-1', { name: 'Prompting syllabus', root: ref('ProcessNode', 'unit-1'),
    outcomes: [ref('LearningOutcome', 'outcome-1')], strategies: [], assessmentSpecs: [] }),
  entity('ProcessNode', 'unit-1', { name: 'Prepare a prompt', kind: 'UNIT', children: [], strategies: [],
    activities: [ref('ActivityDefinition', 'activity-1')] }),
  entity('ActivityDefinition', 'activity-1', { instruction: 'Complete the worksheet.', intent: 'PRACTICE',
    format: 'CRITERIA_BASED_PRODUCT', expectedEvidence: [] }),
  entity('LearningOutcome', 'outcome-1', { statement: 'Construct a first prompt.', topics: [] }),
  entity('ChangeProposal', 'p-1', { status: 'AWAITING_DECISION', proposedChange: 'Review the exact ASSESSMENT output.' }),
];
const signedIn: Reply = { status: 200, body: SESSION };
const summary = (entities: unknown[]): Reply => ({ status: 200, body: { context: CONTEXT, entities, findings: [] } });
const pending = (count: number): Reply => ({ status: 200, body: { proposals: Array.from({ length: count }, () => ({
  proposal: ENTITIES[5], candidates: [], review_payload_key: 'k' })) } });

afterEach(cleanup);

describe('course page', () => {
  it('shows the course in sections and links to the review inbox', async () => {
    const { requests } = await renderStudio({ 'GET /auth/session': [signedIn],
      'GET /contexts/ctx': [summary(ENTITIES)], 'GET /contexts/ctx/pending-proposals': [pending(1)] }, '/studio/contexts/ctx/course');
    expect(await screen.findByText('Prompting syllabus')).toBeTruthy();
    expect(screen.getByText('Status: Draft · Mode: Authoring')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Review inbox: 1 proposal awaits a decision' }).getAttribute('href'))
      .toBe('/studio/contexts/ctx/review');
    const contents = within(screen.getByRole('navigation', { name: en.course.contents }));
    expect(contents.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
      '#course-structure', '#course-outcomes', '#course-strategies', '#course-assessments', '#course-materials', '#course-history']);
    const structure = within(screen.getByRole('region', { name: en.course.structure.heading }));
    expect(structure.getByText('Prepare a prompt')).toBeTruthy();
    expect(structure.getByText('Complete the worksheet.')).toBeTruthy();
    expect(within(screen.getByRole('region', { name: en.course.outcomes.heading })).getByText('Construct a first prompt.')).toBeTruthy();
    expect(screen.getByText(en.course.assessments.empty)).toBeTruthy();
    const history = within(screen.getByRole('region', { name: en.course.history.heading }));
    expect(history.getByRole('link', { name: en.course.history.review }).getAttribute('href')).toBe('/studio/contexts/ctx/review/p-1');
    expect(requests.every((request) => request.method === 'GET')).toBe(true);
  });

  it('says so when the subject cannot see the course content', async () => {
    await renderStudio({ 'GET /auth/session': [signedIn],
      'GET /contexts/ctx': [summary([CONTEXT])], 'GET /contexts/ctx/pending-proposals': [pending(0)] }, '/studio/contexts/ctx/course');
    expect((await screen.findByText(en.course.notVisible)).getAttribute('role')).toBe('status');
  });
});
