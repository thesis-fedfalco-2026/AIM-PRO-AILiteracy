import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import en from '../src/i18n/en.json';
import type { Reply } from './harness';
import { renderStudio, SESSION } from './harness';

const provenance = { origin: 'GENERATED_PROPOSAL', responsible: 'admin', sources: [] };
const entity = (type: string, id: string, version: string, fields: Record<string, unknown>) =>
  ({ type, id, version, fields, provenance });

const CONTEXT = entity('ExecutionContext', 'ctx', 'c1', { status: 'ACTIVE' });
const CLARITY = { key: 'clarity', description: 'The task is clear.',
  levels: [{ key: 'unclear', descriptor: 'The task cannot be identified.' }, { key: 'clear', descriptor: 'The task is stated.' }] };
const RUBRIC = entity('Rubric', 'rubric-1', 'r1', { name: 'Essay rubric', criteria: [CLARITY] });
const EXPLANATION = 'Review the exact ASSESSMENT output. {"generator_gaps":["Synthetic output"],'
  + '"source_diagnostics":[{"code":"ENUM_VALUE","field":"category","value":"DIGITAL","allowed":["Digital"],"object_name":"D04"}]}';
const PENDING = entity('ChangeProposal', 'p-1', '1', {
  status: 'AWAITING_DECISION', proposedChange: EXPLANATION, findings: [], baseContextVersion: 'c1',
});
const CANDIDATES = [
  entity('Rubric', 'rubric-1', 'r2', { name: 'Essay rubric',
    criteria: [CLARITY, { key: 'accuracy', description: 'The answer is accurate.', levels: [] }] }),
  entity('ActivityDefinition', 'activity-1', 'a1', { instruction: 'Write a prompt for a business task.\nHand in one page.',
    expectedEvidence: ['CRITERIA_BASED_PRODUCT'] }),
  entity('AssessmentSpecification', 'spec-1', 's1', { administrationConstraints: ['One evening workshop'],
    allowedEvidence: ['CRITERIA_BASED_PRODUCT'] }),
  entity('Topic', 'topic-1', 't1', { name: 'Sources' }),
];
const APPROVED = entity('ChangeProposal', 'p-2', '7', { status: 'APPROVED', proposedChange: 'Release the project', findings: [] });
const APPLIED = entity('ChangeProposal', 'p-3', '4', { status: 'APPLIED', proposedChange: 'Initialize a project', findings: [] });
const KEY = 'key-1';

const summary = (...proposals: unknown[]): Reply => ({
  status: 200, body: { context: CONTEXT, entities: [CONTEXT, RUBRIC, ...proposals], findings: [] },
});
const pending = (...items: unknown[]): Reply => ({
  status: 200, body: { proposals: items.length ? [{ proposal: PENDING, candidates: CANDIDATES, review_payload_key: KEY }] : [] },
});
const signedIn: Reply = { status: 200, body: SESSION };
const error = (status: number, detail = 'x'): Reply => ({ status, body: { error: 'e', detail, request_id: 'r' } });
const withStatus = (proposal: ReturnType<typeof entity>, status: string, version: string) =>
  ({ ...proposal, version, fields: { ...proposal.fields, status } });

const SUMMARY = 'GET /contexts/ctx';
const PENDING_LIST = 'GET /contexts/ctx/pending-proposals';
const DECIDE = 'POST /contexts/ctx/decisions';
const APPLY = 'POST /contexts/ctx/applications';

const bodyOf = async (request: Request) => JSON.parse(await request.text()) as Record<string, unknown>;
const writes = (requests: Request[]) => requests.filter((request) => request.method === 'POST');

afterEach(cleanup);

describe('home', () => {
  it('opens the review inbox of the context entered', async () => {
    const { router } = await renderStudio({ 'GET /auth/session': [signedIn] });
    const field = await screen.findByLabelText(en.home.contextLabel);
    fireEvent.click(screen.getByRole('button', { name: en.home.open }));
    expect(screen.getByText(en.home.contextRequired)).toBeTruthy();
    expect(field.getAttribute('aria-invalid')).toBe('true');
    fireEvent.change(field, { target: { value: ' my context ' } });
    fireEvent.click(screen.getByRole('button', { name: en.home.open }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/studio/contexts/my%20context/review'));
  });
});

describe('review inbox', () => {
  it('lists the proposals awaiting a decision and the approved ones not yet applied', async () => {
    await renderStudio({
      'GET /auth/session': [signedIn], [SUMMARY]: [summary(PENDING, APPROVED, APPLIED)], [PENDING_LIST]: [pending(1)],
    }, '/studio/contexts/ctx/review');
    const awaiting = within((await screen.findByRole('heading', { name: en.review.inbox.pendingHeading })).closest('section')!);
    const link = awaiting.getByRole('link', { name: 'Proposed assessment: Write a prompt for a business task.' });
    expect(link.getAttribute('href')).toBe('/studio/contexts/ctx/review/p-1');
    expect(awaiting.getByText('Proposed by admin · Points to check: 1')).toBeTruthy();
    const approved = within(screen.getByRole('heading', { name: en.review.inbox.approvedHeading }).closest('section')!);
    expect(approved.getAllByRole('link').map((item) => item.textContent)).toEqual(['Release the project']);
    expect(screen.queryByText('Initialize a project')).toBeNull();
  });

  it('says when nothing awaits a person', async () => {
    await renderStudio({
      'GET /auth/session': [signedIn], [SUMMARY]: [summary(APPLIED)], [PENDING_LIST]: [pending()],
    }, '/studio/contexts/ctx/review');
    expect(await screen.findByText(en.review.inbox.pendingEmpty)).toBeTruthy();
    expect(screen.getByText(en.review.inbox.approvedEmpty)).toBeTruthy();
  });

  it('reports an unavailable context and reads it again on request', async () => {
    const { requests } = await renderStudio({
      'GET /auth/session': [signedIn], [SUMMARY]: [error(404), summary()], [PENDING_LIST]: [error(404), pending()],
    }, '/studio/contexts/ctx/review');
    expect((await screen.findByRole('alert')).textContent).toBe(en.review.errors.unavailable);
    await act(async () => screen.getByRole('button', { name: en.review.errors.retry }).click());
    expect(await screen.findByText(en.review.inbox.pendingEmpty)).toBeTruthy();
    expect(requests.filter((request) => request.url.endsWith('/pending-proposals'))).toHaveLength(2);
  });

  it('returns to sign-in when the session has ended', async () => {
    await renderStudio({
      'GET /auth/session': [signedIn, { status: 401 }], [SUMMARY]: [error(401)], [PENDING_LIST]: [error(401)],
    }, '/studio/contexts/ctx/review');
    expect(await screen.findByRole('button', { name: en.session.signIn })).toBeTruthy();
  });
});

describe('proposal review', () => {
  const open = (replies: Record<string, Reply[]>) =>
    renderStudio({ 'GET /auth/session': [signedIn], ...replies }, '/studio/contexts/ctx/review/p-1');

  it('shows the teaching content, its changes and what to check in plain words', async () => {
    await open({ [SUMMARY]: [summary(PENDING)], [PENDING_LIST]: [pending(1)] });
    expect(await screen.findByText(en.review.teacher.titleAssessment)).toBeTruthy();
    expect(screen.getByTestId('proposal-status').textContent).toBe(en.review.status.awaitingDecision);
    const section = (name: string) => within(screen.getByRole('heading', { name }).closest('section')!);

    expect(section(en.review.teacher.changes.heading).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Assessment criterion added: The answer is accurate.',
      'A new student activity is added.',
      'A new assessment is added.',
    ]);
    const students = section(en.review.teacher.students.heading);
    expect(students.getByText(/Write a prompt for a business task\.\s+Hand in one page\./)).toBeTruthy();
    expect(students.getByText('What students hand in: Criteria based product')).toBeTruthy();
    const assessed = section(en.review.teacher.assessed.heading);
    expect(assessed.getAllByRole('rowheader').map((cell) => cell.textContent)).toEqual(['The task is clear.', 'The answer is accurate.']);
    expect(assessed.getByText('The task cannot be identified.')).toBeTruthy();
    expect(assessed.getByText('One evening workshop')).toBeTruthy();
    const issues = section(en.review.teacher.issues.heading);
    expect(issues.getByText('In the course and its source material, not caused by this proposal (1)').closest('details')!
      .hasAttribute('open')).toBe(false);
    expect(issues.getByText('“D04”: the category “DIGITAL” is not one of the allowed values (Digital).')).toBeTruthy();
    expect(issues.getByText('Synthetic output')).toBeTruthy();
  });

  it('keeps identifiers, the raw diagnostics, the field diff and the exact payload in closed technical details', async () => {
    await open({ [SUMMARY]: [summary(PENDING)], [PENDING_LIST]: [pending(1)] });
    const details = await screen.findByTestId('technical-details');
    expect(details.hasAttribute('open')).toBe(false);
    const technical = within(details);
    expect(technical.getByText(KEY)).toBeTruthy();
    const diagnostics = within(technical.getByRole('heading', { name: en.review.diagnostics.heading }).closest('section')!);
    expect(diagnostics.getByRole('heading', { name: 'Generator gaps' })).toBeTruthy();
    expect(diagnostics.getByRole('cell', { name: 'ENUM_VALUE' })).toBeTruthy();

    const changes = within(technical.getByRole('heading', { name: en.review.changes.heading }).closest('section')!);
    const rubric = changes.getByText('Rubric · Essay rubric').closest('details')!;
    expect(within(rubric).getByText('1 change')).toBeTruthy();
    expect(within(rubric).getByRole('rowheader', { name: 'criteria[1]' })).toBeTruthy();
    expect(within(rubric).getByText(en.review.changes.absent)).toBeTruthy();
    const topic = changes.getByText('Topic · Sources').closest('details')!;
    expect(within(topic).getByText(en.review.changes.new)).toBeTruthy();
    expect(within(topic).getByText(en.review.changes.notApplied)).toBeTruthy();

    const payload = JSON.parse(technical.getByTestId('exact-payload').textContent!) as { proposal: unknown; candidates: unknown };
    expect(payload).toEqual({ proposal: PENDING, candidates: CANDIDATES });
  });

  it('records the decision on the exact revision and key shown, then shows the separate apply step', async () => {
    const approved = withStatus(PENDING, 'APPROVED', '2');
    const { requests } = await open({
      [SUMMARY]: [summary(PENDING), summary(approved)], [PENDING_LIST]: [pending(1), pending()],
      [DECIDE]: [{ status: 200, body: entity('HumanDecision', 'd-1', '1', { decision: 'APPROVE' }) }],
    });
    fireEvent.click(await screen.findByRole('radio', { name: en.review.decision.approve }));
    fireEvent.change(screen.getByLabelText(en.review.decision.reason), { target: { value: '  Checked against the syllabus  ' } });
    await act(async () => screen.getByRole('button', { name: en.review.decision.submit }).click());

    const [decision] = writes(requests);
    expect(decision!.headers.get('X-CSRF-Token')).toBe('csrf-1');
    expect(await bodyOf(decision!)).toEqual({
      target: { type: 'ChangeProposal', id: 'p-1', version: '1' }, decision: 'APPROVE',
      reason: 'Checked against the syllabus', review_payload_key: KEY,
    });
    expect((await screen.findByRole('status')).textContent).toBe('Decision recorded: Approve.');
    expect(await screen.findByRole('button', { name: en.review.apply.submit })).toBeTruthy();
    expect(screen.getByTestId('proposal-status').textContent).toBe(en.review.status.approved);
    expect(screen.queryByRole('button', { name: en.review.decision.submit })).toBeNull();
    expect(writes(requests)).toHaveLength(1);
  });

  it('asks for a decision and a reason before sending anything', async () => {
    const { requests } = await open({ [SUMMARY]: [summary(PENDING)], [PENDING_LIST]: [pending(1)] });
    const submit = await screen.findByRole('button', { name: en.review.decision.submit });
    fireEvent.click(submit);
    expect(screen.getByText(en.review.decision.choiceRequired)).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: en.review.decision.approve }));
    fireEvent.click(screen.getByRole('radio', { name: en.review.decision.reject }));
    fireEvent.change(screen.getByLabelText(en.review.decision.reason), { target: { value: '   ' } });
    fireEvent.click(submit);
    expect(screen.getByText(en.review.decision.reasonRequired)).toBeTruthy();
    expect(screen.getByLabelText(en.review.decision.reason).getAttribute('aria-invalid')).toBe('true');
    expect(writes(requests)).toEqual([]);
  });

  it('reloads after a 409 and shows the state another reviewer left', async () => {
    const rejected = withStatus(PENDING, 'REJECTED', '2');
    const { requests } = await open({
      [SUMMARY]: [summary(PENDING), summary(rejected)], [PENDING_LIST]: [pending(1), pending()],
      [DECIDE]: [error(409, 'Reviewed payload or revision is no longer current')],
    });
    fireEvent.click(await screen.findByRole('radio', { name: en.review.decision.approve }));
    fireEvent.change(screen.getByLabelText(en.review.decision.reason), { target: { value: 'Fine' } });
    await act(async () => screen.getByRole('button', { name: en.review.decision.submit }).click());

    expect((await screen.findByRole('alert')).textContent).toBe(en.review.decision.conflict);
    await waitFor(() => expect(screen.getByTestId('proposal-status').textContent).toBe(en.review.status.rejected));
    expect(screen.getByText(`This proposal does not await a decision. Its status is: ${en.review.status.rejected}.`)).toBeTruthy();
    expect(screen.queryByRole('button', { name: en.review.decision.submit })).toBeNull();
    expect(requests.filter((request) => request.url.endsWith('/pending-proposals'))).toHaveLength(2);
  });

  it('retries an application without an answer with the same operation id', async () => {
    const approved = withStatus(PENDING, 'APPROVED', '2');
    const change = entity('StateChange', 'change-1', '1', { newVersion: 'c2' });
    const { requests } = await open({
      [SUMMARY]: [summary(approved), summary(withStatus(PENDING, 'APPLIED', '3'))], [PENDING_LIST]: [pending(), pending()],
      [APPLY]: ['network', { status: 200, body: change }],
    });
    const apply = await screen.findByRole('button', { name: en.review.apply.submit });
    await act(async () => apply.click());
    expect((await screen.findByRole('alert')).textContent).toBe(en.review.apply.failed);
    await act(async () => screen.getByRole('button', { name: en.review.apply.submit }).click());
    expect((await screen.findByRole('status')).textContent).toBe('Change applied. The context is now at version c2.');
    await waitFor(() => expect(screen.getByTestId('proposal-status').textContent).toBe(en.review.status.applied));

    const bodies = await Promise.all(writes(requests).map(bodyOf));
    const target = { type: 'ChangeProposal', id: 'p-1', version: '2' };
    expect(bodies).toEqual([{ proposal: target, operation_id: 'operation-1' }, { proposal: target, operation_id: 'operation-1' }]);
    expect(writes(requests).every((request) => request.headers.get('X-CSRF-Token') === 'csrf-1')).toBe(true);
  });

  it('reloads when the approval no longer holds at application', async () => {
    const approved = withStatus(PENDING, 'APPROVED', '2');
    await open({
      [SUMMARY]: [summary(approved), summary(withStatus(PENDING, 'REJECTED', '3'))], [PENDING_LIST]: [pending(), pending()],
      [APPLY]: [error(422, 'Proposal is not approved')],
    });
    const apply = await screen.findByRole('button', { name: en.review.apply.submit });
    await act(async () => apply.click());
    expect((await screen.findByRole('alert')).textContent)
      .toBe('The proposal can no longer be applied as approved: Proposal is not approved The page now shows its current state.');
    await waitFor(() => expect(screen.getByTestId('proposal-status').textContent).toBe(en.review.status.rejected));
    expect(screen.queryByRole('button', { name: en.review.apply.submit })).toBeNull();
  });

  it('says when the proposal does not exist in the context', async () => {
    await renderStudio({ 'GET /auth/session': [signedIn], [SUMMARY]: [summary()], [PENDING_LIST]: [pending()] },
      '/studio/contexts/ctx/review/nowhere');
    expect((await screen.findByRole('alert')).textContent).toBe('There is no proposal nowhere in this context.');
    expect(screen.getByRole('link', { name: en.review.proposal.back }).getAttribute('href')).toBe('/studio/contexts/ctx/review');
  });
});
