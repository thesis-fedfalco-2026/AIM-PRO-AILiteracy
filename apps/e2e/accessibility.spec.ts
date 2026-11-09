import { cli, en, expect, expectAccessible, test } from './support';

// axe (WCAG 2.1 A and AA rules) on every view of the review inbox, in the states
// a reviewer meets: lists, the full proposal, validation errors, the apply step,
// a conflict and an unavailable context.
test('the review inbox views pass the axe check', async ({ page, seed }) => {
  const [proposal] = seed.pending_proposals[seed.authoring_context]!;
  const inbox = `/studio/contexts/${seed.authoring_context}/review`;

  await page.goto('/studio/');
  await expect(page.getByLabel(en.home.contextLabel)).toBeVisible();
  await expectAccessible(page);
  await page.getByRole('button', { name: en.home.open }).click();
  await expect(page.getByText(en.home.contextRequired)).toBeVisible();
  await expectAccessible(page);

  await page.goto(inbox);
  await expect(page.getByRole('region', { name: en.review.inbox.pendingHeading }).getByRole('link')).toHaveCount(1);
  await expectAccessible(page);

  await page.goto(`${inbox}/${proposal!.id}`);
  await expect(page.getByRole('button', { name: en.review.decision.submit })).toBeVisible();
  await page.locator('details').evaluateAll((all) => all.forEach((details) => { (details as HTMLDetailsElement).open = true; }));
  await expectAccessible(page);

  await page.getByRole('button', { name: en.review.decision.submit }).click();
  await expect(page.getByText(en.review.decision.choiceRequired)).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('radio', { name: en.review.decision.approve }).check();
  await page.getByLabel(en.review.decision.reason).fill('Accessible review.');
  await page.getByRole('button', { name: en.review.decision.submit }).click();
  await expect(page.getByRole('button', { name: en.review.apply.submit })).toBeVisible();
  await expectAccessible(page);

  // Another reviewer revokes the approval; the application is refused and the page reloads.
  const revoke = cli(seed.staff, seed.authoring_context, ['show']);
  const current = (revoke.output as { entities: { type: string; id: string; version: string }[] }).entities
    .find((entity) => entity.type === 'ChangeProposal' && entity.id === proposal!.id)!;
  const rejected = cli(seed.staff, seed.authoring_context,
    ['decide', JSON.stringify({ type: current.type, id: current.id, version: current.version }), 'REJECT', '--reason', 'Revoked']);
  expect(rejected.status, rejected.errors).toBe(0);
  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.rejected);
  await expectAccessible(page);

  await page.goto(inbox);
  await expect(page.getByText(en.review.inbox.pendingEmpty)).toBeVisible();
  await expectAccessible(page);

  await page.goto(`/studio/contexts/${seed.delivery_context}/review`);
  await expect(page.getByRole('alert')).toHaveText(en.review.errors.unavailable);
  await expectAccessible(page);
});
