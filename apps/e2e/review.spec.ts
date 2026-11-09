import { cli, en, expect, shown, test } from './support';
import type { Entity, EntityRef, SeedManifest } from './support';

const EVALUATOR_SUMMARY = 'Review the exact ASSESSMENT output and host-composed project revision.';
const REASON = 'Checked in the browser test against the synthetic syllabus.';

const evaluatorProposal = (seed: SeedManifest): EntityRef => {
  const [proposal] = seed.pending_proposals[seed.authoring_context]!;
  return proposal!;
};
const proposalUrl = (seed: SeedManifest) =>
  `/studio/contexts/${seed.authoring_context}/review/${evaluatorProposal(seed).id}`;
const about = (entities: Entity[], proposal: EntityRef) => ({
  proposal: entities.find((entity) => entity.type === 'ChangeProposal' && entity.id === proposal.id)!,
  decisions: entities.filter((entity) => entity.type === 'HumanDecision'
    && (entity.fields.target as EntityRef).id === proposal.id),
  changes: entities.filter((entity) => entity.type === 'StateChange'
    && (entity.fields.cause as EntityRef).id === proposal.id),
  context: entities.find((entity) => entity.type === 'ExecutionContext')!,
});

test('a reviewer reviews and applies the Evaluator proposal of the seed', async ({ page, seed }) => {
  const proposal = evaluatorProposal(seed);
  await page.goto('/studio/');
  await page.getByLabel(en.home.contextLabel).fill(seed.authoring_context);
  await page.getByRole('button', { name: en.home.open }).click();

  const awaiting = page.getByRole('region', { name: en.review.inbox.pendingHeading });
  await awaiting.getByRole('link', { name: EVALUATOR_SUMMARY }).click();
  await expect(page).toHaveURL(proposalUrl(seed));
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.awaitingDecision);

  // Diagnostics of the generator report and the comparison with the applied assessment.
  const diagnostics = page.getByRole('region', { name: en.review.diagnostics.heading });
  await expect(diagnostics.getByRole('heading', { name: 'Contract findings' })).toBeVisible();
  await expect(diagnostics.getByRole('heading', { name: 'Source diagnostics' })).toBeVisible();
  const changes = page.getByRole('region', { name: en.review.changes.heading });
  await expect(changes.locator('details[data-status="changed"]').first()).toBeVisible();
  await expect(changes.locator('details').filter({ hasText: /^AssessmentSpecification · / })).toHaveCount(1);

  // Approval, then application: two separate steps.
  await page.getByRole('radio', { name: en.review.decision.approve }).check();
  await page.getByLabel(en.review.decision.reason).fill(REASON);
  await page.getByRole('button', { name: en.review.decision.submit }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Decision recorded' })).toHaveText('Decision recorded: Approve.');
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.approved);

  const approved = about(shown(seed.authoring_context), proposal);
  expect(approved.proposal.fields.status).toBe('APPROVED');
  expect(approved.decisions.map((d) => [d.fields.decision, d.fields.reason, d.fields.target, d.fields.reviewedPayloadKey]))
    .toEqual([['APPROVE', REASON, proposal, approved.proposal.fields.reviewPayloadKey]]);
  expect(approved.changes).toEqual([]);

  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Change applied' })).toBeVisible();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.applied);

  const applied = about(shown(seed.authoring_context), proposal);
  expect(applied.proposal.fields.status).toBe('APPLIED');
  expect(applied.changes).toHaveLength(1);
  expect(applied.changes[0]!.fields.newVersion).toBe(applied.context.version);
  await expect(page.getByRole('status').filter({ hasText: 'Change applied' }))
    .toHaveText(`Change applied. The context is now at version ${applied.context.version}.`);

  await page.getByRole('link', { name: en.review.proposal.back }).click();
  await expect(page.getByText(en.review.inbox.pendingEmpty)).toBeVisible();
  await expect(page.getByText(en.review.inbox.approvedEmpty)).toBeVisible();
});

test('a proposal decided by another reviewer after loading is refused and reloaded', async ({ page, seed }) => {
  const proposal = evaluatorProposal(seed);
  await page.goto(proposalUrl(seed));
  await expect(page.getByRole('button', { name: en.review.decision.submit })).toBeVisible();

  // Another reviewer rejects through the CLI while the page is open.
  const other = cli(seed.staff, seed.authoring_context,
    ['decide', JSON.stringify(proposal), 'REJECT', '--reason', 'Rejected from the CLI']);
  expect(other.status, other.errors).toBe(0);

  await page.getByRole('radio', { name: en.review.decision.approve }).check();
  await page.getByLabel(en.review.decision.reason).fill(REASON);
  await page.getByRole('button', { name: en.review.decision.submit }).click();

  await expect(page.getByRole('alert')).toHaveText(en.review.decision.conflict);
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.rejected);
  await expect(page.getByRole('button', { name: en.review.decision.submit })).toHaveCount(0);
  await expect(page.getByRole('button', { name: en.review.apply.submit })).toHaveCount(0);

  const after = about(shown(seed.authoring_context), proposal);
  expect(after.decisions.map((d) => [d.fields.decision, d.fields.reason])).toEqual([['REJECT', 'Rejected from the CLI']]);
  expect(after.proposal.fields.status).toBe('REJECTED');
});

test('an application whose answer is lost is retried with the same operation id', async ({ page, seed }) => {
  const proposal = evaluatorProposal(seed);
  const approval = cli(seed.staff, seed.authoring_context, ['decide', JSON.stringify(proposal), 'APPROVE', '--reason', REASON]);
  expect(approval.status, approval.errors).toBe(0);

  const operations: string[] = [];
  await page.route('**/contexts/*/applications', async (route) => {
    operations.push((route.request().postDataJSON() as { operation_id: string }).operation_id);
    if (operations.length === 1) {
      await route.fetch(); // The API applies the change; the browser never sees the answer.
      await route.abort('failed');
    } else {
      await route.continue();
    }
  });

  await page.goto(proposalUrl(seed));
  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByRole('alert')).toHaveText(en.review.apply.failed);
  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Change applied' })).toBeVisible();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.applied);

  expect(operations).toHaveLength(2);
  expect(operations[1]).toBe(operations[0]);
  expect(about(shown(seed.authoring_context), proposal).changes).toHaveLength(1);
});
