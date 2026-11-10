import type { Page } from '@playwright/test';

import { AIMPRO_EXPORT } from './stack/paths.mjs';
import { en, expect, expectAccessible, test } from './support';

const COURSE = 'prompting-refined';
const REASON = 'Synthetic review of the exact payload';
// The marker makes the synthetic reviewer reject the first draft of the revision (tests/syllabus_fixtures.py).
const REVISION = 'Add a unit where participants explain two prompting choices. [synthetic reviewer: reject the first draft]';

async function decide(page: Page, decision: string, reason: string) {
  await page.getByRole('radio', { name: decision }).check();
  await page.getByLabel(en.review.decision.reason).fill(reason);
  await page.getByRole('button', { name: en.review.decision.submit }).click();
}

async function approveAndApply(page: Page) {
  await decide(page, en.review.decision.approve, REASON);
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.approved);
  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.applied);
}

const openDetails = (page: Page) =>
  page.locator('details').evaluateAll((all) => all.forEach((details) => { (details as HTMLDetailsElement).open = true; }));

// Acceptance (S09b): the syllabus in words; a revision request reaches the Curator and the revision is compared with
// the previous proposal; a teacher's edit is a new proposal compared with the one it edits; after each applied step
// the course shows the applied syllabus. Chat 20: the review agent's assessment of each draft of the revision.
test('a syllabus is refined with the Curator and by the teacher, step by step', async ({ page }) => {
  await page.goto('/studio/');
  await page.getByLabel(en.home.courseLabel).fill(COURSE);
  await page.getByRole('button', { name: en.home.create }).click();
  await expect(page).toHaveURL(`/studio/contexts/${COURSE}/build`);
  await page.getByLabel(en.build.upload.file).setInputFiles(AIMPRO_EXPORT);
  await page.getByRole('button', { name: en.build.upload.submit }).click();
  await expect(page.getByText(en.build.upload.stored)).toBeVisible();
  await page.getByLabel(en.build.curator.scope, { exact: true }).fill('wp3');
  await page.getByLabel(en.build.curator.query).fill('prompting');
  await page.getByRole('button', { name: en.build.curator.submit }).click();
  await expect(page.getByText(en.build.curator.proposed)).toBeVisible({ timeout: 30_000 });
  await page.getByRole('link', { name: en.build.curator.review }).click();

  // The syllabus in words, compared with a course that has none yet.
  await expect(page.getByText(en.review.teacher.titleSyllabus)).toBeVisible();
  const units = page.getByRole('region', { name: 'The syllabus: Synthetic business prompting syllabus' });
  await expect(units).toContainText('AI Interaction & Prompting');
  await expect(units).toContainText('Modelling AI practices');
  await expect(units).toContainText('Explanation or demonstration, Guided practice');
  const current = page.getByRole('region', { name: en.review.syllabus.compare.currentHeading });
  await expect(current).toContainText(en.review.syllabus.compare.noSyllabus);
  await expect(page.getByText(en.review.teacher.changes.none)).toHaveCount(0);
  await openDetails(page);
  await expectAccessible(page);

  // A revision request, then the Curator's revision, compared with the proposal it revises.
  await decide(page, en.review.decision.requestRevision, REVISION);
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.draft);
  await expect(page.getByText(`You asked for a revision: “${REVISION}”`)).toBeVisible();
  await page.getByRole('button', { name: en.review.syllabus.revision.ask }).click();
  // Chat 20: the review agent rejected the first draft and accepted the second; the teacher reads both
  // assessments, the agent's reason labelled as model text.
  const open = page.getByRole('link', { name: en.review.syllabus.revision.open });
  await expect(open).toBeVisible({ timeout: 30_000 });
  await page.getByText(en.build.reviews.summary).click();
  const attempts = page.getByTestId('review-attempts');
  await expect(attempts).toContainText(`Draft 1: ${en.build.reviews.outcome.rejected}`);
  await expect(attempts).toContainText('(model text): “Synthetic reviewer text: the cited excerpt does not support the unit claim.”');
  await expect(attempts).toContainText(`Draft 2: ${en.build.reviews.outcome.accepted}`);
  await expectAccessible(page);
  await open.click();
  const revised = page.getByRole('region', { name: en.review.syllabus.compare.revisedHeading });
  await expect(revised).toContainText(en.review.syllabus.compare.titleChanged);
  await expect(revised.locator('[data-status]')).toHaveCount(2);
  await expect(revised.locator('[data-status="CHANGED"]')).toContainText(en.review.syllabus.field.purpose);
  await expect(revised.locator('[data-status="ADDED"]')).toContainText('Explain two prompting choices');
  await expect(page.getByRole('region', { name: /The syllabus:/ })).toContainText(REVISION);
  await openDetails(page);
  await expectAccessible(page);

  // First applied step: the course follows the revised syllabus.
  const revisedPage = page.url();
  await approveAndApply(page);
  await page.goto(`/studio/contexts/${COURSE}/course`);
  const structure = page.getByRole('region', { name: en.course.structure.heading });
  await expect(structure).toContainText('Syllabus in use: Synthetic business prompting syllabus, revised');
  await expect(structure).toContainText('Explain two prompting choices');

  // The teacher edits the applied syllabus: a new proposal by the teacher, compared with the syllabus in use.
  await page.goto(revisedPage);
  await page.getByRole('link', { name: en.review.syllabus.edit.open }).click();
  await expect(page.getByRole('heading', { name: en.review.syllabus.edit.heading, level: 1 })).toBeVisible();
  await page.getByLabel(en.review.syllabus.edit.title).fill('Business prompting, the teacher’s version');
  const second = page.getByTestId('syllabus-unit').nth(1);
  await second.getByLabel(en.review.syllabus.field.title).fill('Explain your prompting choices to a peer');
  await expectAccessible(page);
  await page.getByRole('button', { name: en.review.syllabus.edit.submit }).click();
  const edited = page.getByRole('region', { name: en.review.syllabus.compare.editedHeading });
  await expect(edited).toBeVisible();
  await expect(edited).toContainText(en.review.syllabus.compare.titleChanged);
  await expect(edited.locator('[data-status="UNCHANGED"]')).toHaveCount(1);
  await expect(edited.locator('[data-status="CHANGED"]')).toContainText('Explain your prompting choices to a peer');
  await expect(page.getByRole('region', { name: /The syllabus:/ })).toContainText('Edited by');
  const withCourse = page.getByRole('region', { name: en.review.syllabus.compare.currentHeading });
  await expect(withCourse).toContainText('The course follows the syllabus “Synthetic business prompting syllabus, revised”');

  // Second applied step: the course follows the teacher's syllabus.
  await approveAndApply(page);
  await page.goto(`/studio/contexts/${COURSE}/course`);
  await expect(structure).toContainText('Syllabus in use: Business prompting, the teacher’s version');
  await expect(structure).toContainText('Explain your prompting choices to a peer');
  await expect(structure).toContainText('Edited by');
  await expectAccessible(page);
});
