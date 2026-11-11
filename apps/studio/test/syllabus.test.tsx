import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import en from '../src/i18n/en.json';
import type { Reply } from './harness';
import { renderStudio, SESSION } from './harness';
import { firstView, revisedView } from './syllabus-fixture';

const provenance = { origin: 'GENERATED_PROPOSAL', responsible: 'admin', sources: [] };
const entity = (type: string, id: string, version: string, fields: Record<string, unknown>) =>
  ({ type, id, version, fields, provenance });

const CONTEXT = entity('ExecutionContext', 'ctx', 'c1', { status: 'DRAFT', mode: 'PREPARATION' });
const CANDIDATES = [{ type: 'Resource', id: 'aimpro-syllabus-0a1b:syllabus', version: '1' }];
const proposal = (id: string, status: string, fields: Record<string, unknown> = {}) => entity('ChangeProposal', id, '2', {
  status, proposedChange: 'Import a Curator syllabus outline for human review. {"syllabus_gaps":["No rubric yet."]}',
  findings: [], baseContextVersion: 'c1', candidateDefinitions: CANDIDATES, ...fields,
});
const DECISION = entity('HumanDecision', 'decision-1', 'd1', {
  target: { type: 'ChangeProposal', id: 'p-syllabus', version: '1' }, decision: 'REQUEST_REVISION',
  reason: 'Add a unit where participants explain their choices.', decidedAt: '2026-11-10T10:00:00Z',
});

const signedIn: Reply = { status: 200, body: SESSION };
const summary = (...entities: unknown[]): Reply => ({ status: 200, body: { context: CONTEXT, entities: [CONTEXT, ...entities], findings: [] } });
const pending = (...proposals: ReturnType<typeof proposal>[]): Reply => ({ status: 200, body: {
  proposals: proposals.map((item) => ({ proposal: item, candidates: [], review_payload_key: 'key-1' })) } });
const job = (status: string, extra: Record<string, unknown> = {}) => ({
  context_id: 'ctx', request_id: 'request-1', subject_key: 'admin', status, proposal_refs: [], detail: null,
  created: 't', updated: 't', job: { kind: 'revise-aimpro-syllabus', proposal: 'p-syllabus' }, ...extra,
});

afterEach(cleanup);

describe('syllabus proposal', () => {
  it('is shown in words, compared with a course that has no syllabus yet', async () => {
    await renderStudio({
      'GET /auth/session': [signedIn], 'GET /contexts/ctx': [summary(proposal('p-syllabus', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/pending-proposals': [pending(proposal('p-syllabus', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/syllabus-proposals/p-syllabus': [{ status: 200, body: firstView() }],
    }, '/studio/contexts/ctx/review/p-syllabus');
    const units = await screen.findByRole('region', { name: /The syllabus: Business prompting/ });
    expect(screen.getByText(en.review.teacher.titleSyllabus)).toBeTruthy();
    expect(within(units).getByText('Construct a first prompt for a task from one’s own business.')).toBeTruthy();
    expect(within(units).getByText('AI Interaction & Prompting')).toBeTruthy();
    expect(within(units).getByText('Modelling AI practices')).toBeTruthy();
    expect(within(units).getByText('Explanation or demonstration, Guided practice')).toBeTruthy();
    expect(within(units).getByText('Why this source was chosen: Task, audience and tone of a business prompt.')).toBeTruthy();
    expect(within(units).getByText('Limitations: Synthetic excerpt.')).toBeTruthy();
    const current = screen.getByRole('region', { name: en.review.syllabus.compare.currentHeading });
    expect(within(current).getByText(en.review.syllabus.compare.noSyllabus)).toBeTruthy();
    expect(within(current).getByText(en.review.syllabus.status.added)).toBeTruthy();
    // The generic comparison never claims the teaching content is unchanged for a syllabus.
    expect(screen.queryByText(en.review.teacher.changes.none)).toBeNull();
    expect(screen.getByRole('link', { name: en.review.syllabus.edit.open }).getAttribute('href'))
      .toBe('/studio/contexts/ctx/review/p-syllabus/edit');
  });

  it('compares a revision with the proposal it revises, field by field', async () => {
    await renderStudio({
      'GET /auth/session': [signedIn], 'GET /contexts/ctx': [summary(proposal('p-revised', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/pending-proposals': [pending(proposal('p-revised', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/syllabus-proposals/p-revised': [{ status: 200, body: revisedView() }],
    }, '/studio/contexts/ctx/review/p-revised');
    const changes = await screen.findByRole('region', { name: en.review.syllabus.compare.revisedHeading });
    expect(within(changes).getByText(en.review.syllabus.compare.titleChanged)).toBeTruthy();
    const rows = within(changes).getAllByRole('listitem').filter((item) => item.dataset.status);
    expect(rows.map((row) => row.dataset.status)).toEqual(['CHANGED', 'ADDED']);
    expect(within(rows[0]!).getByText(en.review.syllabus.field.purpose)).toBeTruthy();
    expect(within(rows[0]!).getByText('Observe and practice stating a task, audience and tone.')).toBeTruthy();
    expect(within(rows[0]!).getByText('Observe a live prompt, then practice task, audience and tone.')).toBeTruthy();
    expect(within(rows[1]!).getByText(/Explain two prompting choices/)).toBeTruthy();
    expect(screen.getByText('Add a unit where participants explain their choices.')).toBeTruthy();
  });

  it('says when the review agent accepted none of the drafts, with its reason as model text (issue #112)', async () => {
    const view = firstView();
    const rejected = { ...view, syllabus: { ...view.syllabus,
      review: { verdict: 'REJECT', source_alignment: true, citation_support: false, reason: 'A claim exceeds its excerpt.' } } };
    await renderStudio({
      'GET /auth/session': [signedIn], 'GET /contexts/ctx': [summary(proposal('p-syllabus', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/pending-proposals': [pending(proposal('p-syllabus', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/syllabus-proposals/p-syllabus': [{ status: 200, body: rejected }],
    }, '/studio/contexts/ctx/review/p-syllabus');
    const notice = await screen.findByTestId('not-accepted');
    expect(notice.textContent).toBe(en.review.syllabus.notAcceptedByAgent.replace('{{reason}}', 'A claim exceeds its excerpt.'));
    expect(screen.queryByText(/reviewed by the review agent:/)).toBeNull();
    // The decision stays the teacher's: the proposal can still be approved.
    expect(screen.getByRole('radio', { name: en.review.decision.approve })).toBeTruthy();
  });

  it('after a revision request, asks the Curator for a revised syllabus and opens it', async () => {
    const draft = proposal('p-syllabus', 'DRAFT', { decision: { type: 'HumanDecision', id: 'decision-1', version: 'd1' } });
    const { requests } = await renderStudio({
      'GET /auth/session': [signedIn], 'GET /contexts/ctx': [summary(draft, DECISION)],
      'GET /contexts/ctx/pending-proposals': [pending()],
      'GET /contexts/ctx/syllabus-proposals/p-syllabus': [{ status: 200, body: firstView() }],
      'GET /contexts/ctx/jobs': [{ status: 200, body: { jobs: [] } }],
      'POST /contexts/ctx/jobs': [{ status: 200, body: job('QUEUED') }],
      'GET /contexts/ctx/jobs/request-1': [{ status: 200, body: job('PROPOSED', {
        proposal_refs: [{ type: 'ChangeProposal', id: 'p-revised', version: '1' }] }) }],
      'GET /contexts/ctx/syllabus-reviews/request-1': [{ status: 200, body: { request_id: 'request-1', outcome: 'PROPOSAL',
        attempts: [{ attempt: 1, check: null, review: { verdict: 'REJECT', source_alignment: false, citation_support: true,
          reason: 'The new unit drops the demonstration.' } },
        { attempt: 2, check: null, review: { verdict: 'ACCEPT', source_alignment: true, citation_support: true,
          reason: 'Does what was asked.' } }] } }],
    }, '/studio/contexts/ctx/review/p-syllabus');
    expect(await screen.findByText(/You asked for a revision: “Add a unit where participants explain their choices.”/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: en.review.syllabus.revision.ask }));
    const open = await screen.findByRole('link', { name: en.review.syllabus.revision.open });
    expect(open.getAttribute('href')).toBe('/studio/contexts/ctx/review/p-revised');
    // How the review agent judged each draft of the revision, read when the teacher opens it.
    const details = screen.getByText(en.build.reviews.summary).closest('details')!;
    details.open = true;
    fireEvent(details, new Event('toggle'));
    const attempts = within(await screen.findByTestId('review-attempts'));
    expect(attempts.getByText(`Draft 1: ${en.build.reviews.outcome.rejected}`)).toBeTruthy();
    expect(attempts.getByText(/model text\): “The new unit drops the demonstration.”/)).toBeTruthy();
    expect(attempts.getByText(`Draft 2: ${en.build.reviews.outcome.accepted}`)).toBeTruthy();
    const queued = requests.filter((request) => request.method === 'POST');
    expect(await queued[0]!.json()).toEqual({ request_id: 'request-1', job: { kind: 'revise-aimpro-syllabus', proposal: 'p-syllabus' } });
    expect(queued[0]!.headers.get('X-CSRF-Token')).toBe(SESSION.csrf_token);
  });
});

describe('syllabus edit', () => {
  const edit = (replies: Record<string, Reply[]>) => renderStudio({
    'GET /auth/session': [signedIn],
    'GET /contexts/ctx/syllabus-proposals/p-syllabus': [{ status: 200, body: firstView() }], ...replies,
  }, '/studio/contexts/ctx/review/p-syllabus/edit');

  it('proposes the teacher whole syllabus and opens the new proposal', async () => {
    const { requests, router } = await edit({
      'POST /contexts/ctx/syllabus-edits': [{ status: 200, body: { proposal: { type: 'ChangeProposal', id: 'p-edit', version: '1' } } }],
      'GET /contexts/ctx': [summary(proposal('p-edit', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/pending-proposals': [pending(proposal('p-edit', 'AWAITING_DECISION'))],
      'GET /contexts/ctx/syllabus-proposals/p-edit': [{ status: 200, body: revisedView() }],
    });
    const [first] = await screen.findAllByTestId('syllabus-unit');
    fireEvent.change(within(first!).getByLabelText(en.review.syllabus.field.title), { target: { value: ' My unit ' } });
    fireEvent.click(screen.getByRole('button', { name: en.review.syllabus.edit.addUnit }));
    const units = screen.getAllByTestId('syllabus-unit');
    expect(units).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: en.review.syllabus.edit.submit }));
    // The new unit has no title, purpose or claim yet: nothing is sent.
    expect(within(units[1]!).getAllByText(en.review.syllabus.edit.required)).toHaveLength(2);
    expect(requests.filter((request) => request.method === 'POST')).toHaveLength(0);
    fireEvent.click(within(units[1]!).getByRole('button', { name: en.review.syllabus.edit.up }));
    const moved = screen.getAllByTestId('syllabus-unit')[0]!;
    fireEvent.change(within(moved).getByLabelText(en.review.syllabus.field.title), { target: { value: 'Explain two choices' } });
    fireEvent.change(within(moved).getByLabelText(en.review.syllabus.field.purpose), { target: { value: 'Explain choices.' } });
    fireEvent.click(within(moved).getByLabelText(en.review.syllabus.intent.PRACTICE));
    fireEvent.change(within(moved).getByLabelText(en.review.syllabus.edit.claim), { target: { value: 'State the task.' } });
    fireEvent.click(screen.getByRole('button', { name: en.review.syllabus.edit.submit }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/studio/contexts/ctx/review/p-edit'));
    const [sent] = requests.filter((request) => request.method === 'POST');
    const body = await sent!.json() as { request_id: string; proposal: string; draft: { units: Record<string, unknown>[] } };
    expect([body.request_id, body.proposal]).toEqual(['request-1', 'p-syllabus']);
    expect(body.draft.units.map((unit) => [unit.key, unit.title, unit.planned_intents])).toEqual([
      ['unit-2', 'Explain two choices', ['EXPLAIN', 'PRACTICE']],
      ['unit-0', 'My unit', ['EXPLAIN', 'PRACTICE']]]);
    expect(body.draft.units[0]!.source_competency_ids).toEqual(['competency-1']);
  });

  it('shows the fixed reason when the checks refuse the edit', async () => {
    await edit({ 'POST /contexts/ctx/syllabus-edits': [{ status: 422, body: {
      error: 'validation', detail: 'Syllabus must cover exactly the supplied targets', request_id: 'r' } }] });
    fireEvent.click(await screen.findByRole('button', { name: en.review.syllabus.edit.submit }));
    expect(await screen.findByText('Refused: Syllabus must cover exactly the supplied targets')).toBeTruthy();
  });
});
