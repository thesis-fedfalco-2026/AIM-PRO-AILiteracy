import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

import { DATABASE, LEARNER_STATE } from './stack/paths.mjs';
import { en, expect, expectAccessible, test } from './support';

const digest = () => createHash('sha256').update(readFileSync(DATABASE)).digest('hex');

test('the course page shows the whole seeded course and writes nothing', async ({ page, seed }) => {
  const before = digest();
  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.method() !== 'GET') writes.push(`${request.method()} ${request.url()}`);
  });

  await page.goto('/studio/');
  await page.getByLabel(en.home.contextLabel).fill(seed.authoring_context);
  await page.getByRole('button', { name: en.home.open }).click();
  await expect(page).toHaveURL(`/studio/contexts/${seed.authoring_context}/course`);
  await expect(page.getByText('Synthetic business prompting syllabus', { exact: true })).toBeVisible();

  const structure = page.getByRole('region', { name: en.course.structure.heading });
  await expect(structure).toContainText('Prepare a fictional business prompt');
  await expect(structure).toContainText('Compare the weak and improved fictional reminder prompts.');
  await expect(structure).toContainText('Complete the worksheet: write a fictional reminder prompt and explain two choices.');
  await expect(structure).toContainText('Completed when: Every direct child status equals COMPLETED.');

  const outcomes = page.getByRole('region', { name: en.course.outcomes.heading });
  await expect(outcomes).toContainText('Identify relevant prompting choices and construct a first prompt for a task from one’s own business.');
  await expect(outcomes).toContainText('AI Interaction & Prompting');
  await expect(page.getByRole('region', { name: en.course.strategies.heading })).toContainText('ModellingAIPractices');

  const assessments = page.getByRole('region', { name: en.course.assessments.heading });
  await expect(assessments).toContainText('Students: Submit a fictional business reminder prompt and explain two choices.');
  await expect(assessments.getByRole('rowheader')).toHaveText(['The task and fictional audience are identifiable.']);

  const materials = page.getByRole('region', { name: en.course.materials.heading });
  await expect(materials.locator('summary')).toHaveText(['Synthetic EXPLANATION', 'Synthetic TRANSCRIPT', 'Synthetic EXAMPLE', 'Synthetic WORKSHEET']);
  await expect(materials.getByRole('link', { name: 'Synthetic prompting guide' })).toBeVisible();

  const history = page.getByRole('region', { name: en.course.history.heading });
  await expect(history.getByRole('listitem').filter({ hasText: /^Review the exact ASSESSMENT/ }).first()).toBeVisible();
  await expect(history.getByRole('link', { name: en.course.history.review })).toHaveCount(1);
  await expect(history).toContainText('approved by admin');

  await page.locator('details').evaluateAll((all) => all.forEach((details) => { (details as HTMLDetailsElement).open = true; }));
  await expectAccessible(page);

  await page.getByRole('link', { name: 'Review inbox: 1 proposal awaits a decision' }).click();
  await expect(page.getByRole('heading', { name: en.review.inbox.title, level: 1 })).toBeVisible();
  await page.getByRole('link', { name: en.review.inbox.course }).click();
  await expect(page).toHaveURL(`/studio/contexts/${seed.authoring_context}/course`);

  expect(writes).toEqual([]);
  expect(digest()).toBe(before);
});

test.describe('as a learner', () => {
  test.use({ storageState: LEARNER_STATE });

  test('the course page shows no authoring content', async ({ page, seed }) => {
    await page.goto(`/studio/contexts/${seed.pending_delivery_context}/course`);
    await expect(page.getByText(en.course.notVisible)).toBeVisible();
    await expect(page.getByRole('region')).toHaveCount(0);
    await expectAccessible(page);
  });
});
