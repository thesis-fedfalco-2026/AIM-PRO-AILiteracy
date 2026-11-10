import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';

import type { Page } from '@playwright/test';

import { AIMPRO_EXPORT, DATABASE, EXPORTS, SEED } from './stack/paths.mjs';
import { en, expect, expectAccessible, test } from './support';

const COURSE = 'prompting-from-aimpro';
const REASON = 'Synthetic review of the exact payload';

const sha256 = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
const exportsDigests = () => Object.fromEntries(readdirSync(EXPORTS).map((name) => [name, sha256(readFileSync(`${EXPORTS}${name}`))]));

async function createCourse(page: Page) {
  await page.goto('/studio/');
  await page.getByLabel(en.home.courseLabel).fill(COURSE);
  await page.getByRole('button', { name: en.home.create }).click();
  await expect(page).toHaveURL(`/studio/contexts/${COURSE}/build`);
  await expect(page.getByRole('heading', { name: en.build.title, level: 1 })).toBeVisible();
}

/** Approve the proposal on screen with a reason, then apply it. */
async function approveAndApply(page: Page) {
  await page.getByRole('radio', { name: en.review.decision.approve }).check();
  await page.getByLabel(en.review.decision.reason).fill(REASON);
  await page.getByRole('button', { name: en.review.decision.submit }).click();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.approved);
  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.applied);
}

// Acceptance (S09a): upload the AIM-PRO export, run the Curator job with the synthetic model,
// review and apply the syllabus, initialize the project.
test('a course is built from an uploaded AIM-PRO model', async ({ page }) => {
  await createCourse(page);
  // The API wrote one new policy file for the course; the seed's policy is untouched.
  expect(readdirSync(`${SEED}policies`).sort()).toEqual(['architecture-policy-1.json', `course-${COURSE}-1.json`]);

  const uploaded = readFileSync(AIMPRO_EXPORT);
  await page.getByLabel(en.build.upload.file).setInputFiles(AIMPRO_EXPORT);
  await page.getByRole('button', { name: en.build.upload.submit }).click();
  await expect(page.getByText(en.build.upload.stored)).toBeVisible();
  const report = page.getByTestId('export-report');
  await expect(report).toContainText(sha256(uploaded));
  await expect(report).toContainText(en.build.upload.notConforms);
  // The bytes are kept as received, under their digest.
  expect(exportsDigests()[`${sha256(uploaded)}.json`]).toBe(sha256(uploaded));

  await page.getByLabel(en.build.curator.scope).fill('wp3');
  await page.getByLabel(en.build.curator.query).fill('prompting');
  await page.getByRole('button', { name: en.build.curator.submit }).click();
  await expect(page.getByText(en.build.curator.proposed)).toBeVisible({ timeout: 30_000 });
  await page.locator('details').evaluateAll((all) => all.forEach((details) => { (details as HTMLDetailsElement).open = true; }));
  await expectAccessible(page);

  await page.getByRole('link', { name: en.build.curator.review }).click();
  await expect(page.getByRole('heading', { name: en.review.proposal.title, level: 1 })).toBeVisible();
  await expect(page.getByText('Curator syllabus', { exact: false }).first()).toBeVisible();
  await approveAndApply(page);

  // The applied syllabus is the course overview.
  await page.goto(`/studio/contexts/${COURSE}/course`);
  await expect(page.getByRole('region', { name: en.course.structure.heading })).toBeVisible();
  await expect(page.getByText(en.course.notStarted)).toHaveCount(0);

  await page.getByRole('link', { name: en.course.continueBuild }).click();
  await page.getByLabel(en.build.project.label).fill('main');
  await page.getByRole('button', { name: en.build.project.submit }).click();
  await page.getByRole('link', { name: en.build.project.review }).click();
  await approveAndApply(page);

  await page.goto(`/studio/contexts/${COURSE}/build`);
  await expect(page.getByText('Project “main” is initialized.')).toBeVisible();
  expect(exportsDigests()[`${sha256(uploaded)}.json`]).toBe(sha256(uploaded));
});

// Acceptance (S09a2): prepare sources with the synthetic retrieval, review them, accept them, run the Curator
// on them, review and apply the syllabus.
test('a syllabus is built on sources the teacher prepared and accepted', async ({ page }) => {
  await createCourse(page);
  await page.getByLabel(en.build.upload.file).setInputFiles(AIMPRO_EXPORT);
  await page.getByRole('button', { name: en.build.upload.submit }).click();
  await expect(page.getByText(en.build.upload.stored)).toBeVisible();

  await page.getByLabel(en.build.sources.scope).fill('wp3');
  await page.getByLabel(en.build.sources.queries).fill('prompting\nprompt clarity');
  await page.getByRole('button', { name: en.build.sources.search }).click();
  const excerpt = page.getByTestId('discovered-excerpt');
  await expect(excerpt).toHaveCount(1, { timeout: 30_000 });
  await expect(excerpt).toContainText('Found by: prompting, prompt clarity');
  await expect(excerpt).toContainText('Usage conditions: licence CC-BY-4.0');
  await excerpt.getByLabel('Use excerpt 1').check();
  await excerpt.getByLabel(en.build.sources.purpose).fill('Task, audience and tone of a business prompt.');
  await excerpt.getByLabel(en.build.sources.limitations).fill('Synthetic excerpt.\nNot a validated instrument.');
  await page.getByRole('button', { name: en.build.sources.prepare }).click();

  const prepared = page.getByTestId('prepared-sources');
  await expect(prepared).toBeVisible({ timeout: 30_000 });
  await expect(prepared).toContainText('Task, audience and tone of a business prompt.');
  await expect(prepared).toContainText('Synthetic excerpt.; Not a validated instrument.');
  await page.locator('details').evaluateAll((all) => all.forEach((details) => { (details as HTMLDetailsElement).open = true; }));
  await expectAccessible(page);
  // Not accepted yet: the Curator offers no prepared sources.
  await expect(page.getByLabel(en.build.curator.fromSources)).toHaveCount(0);
  await prepared.getByRole('button', { name: en.build.sources.accept }).click();
  await expect(page.getByText(en.build.sources.accepted)).toBeVisible();

  await expect(page.getByLabel(en.build.curator.fromSources)).toBeChecked();
  await page.getByRole('button', { name: en.build.curator.submit }).click();
  await expect(page.getByText(en.build.curator.proposed)).toBeVisible({ timeout: 30_000 });
  await page.getByRole('link', { name: en.build.curator.review }).click();
  await expect(page.getByRole('heading', { name: en.review.proposal.title, level: 1 })).toBeVisible();
  await approveAndApply(page);

  await page.goto(`/studio/contexts/${COURSE}/course`);
  await expect(page.getByRole('region', { name: en.course.structure.heading })).toBeVisible();

  // After leaving the page, its jobs are listed: the search, the accepted preparation and the Curator.
  await page.goto(`/studio/contexts/${COURSE}/build`);
  const jobs = page.getByTestId('course-jobs').getByRole('listitem');
  await expect(jobs).toHaveCount(3);
  await expect(jobs.nth(0)).toContainText('Curator syllabus: proposal waiting for review');
  await expect(jobs.nth(1)).toContainText('Preparation of the sources: accepted');
  await expect(jobs.nth(2)).toContainText('Search of the sources: done');
  await expectAccessible(page);
});

// Acceptance (S09a): an invalid file is refused with its reason; nothing is recorded.
test('an invalid file is refused with its reason and nothing is recorded', async ({ page }) => {
  await createCourse(page);
  const exports = exportsDigests();
  const database = sha256(readFileSync(DATABASE));

  await page.getByLabel(en.build.upload.file).setInputFiles({
    name: 'notes.json', mimeType: 'application/json', buffer: Buffer.from('These are notes, not a model.'),
  });
  await page.getByRole('button', { name: en.build.upload.submit }).click();
  await expect(page.getByRole('alert')).toHaveText('Refused: The file is not UTF-8 JSON');
  await expect(page.getByTestId('export-report')).toHaveCount(0);
  await expect(page.getByText(en.build.curator.needsUpload)).toBeVisible();
  await expectAccessible(page);

  expect(exportsDigests()).toEqual(exports);
  expect(sha256(readFileSync(DATABASE))).toBe(database);
});
