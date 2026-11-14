import { spawnSync } from 'node:child_process';
import { copyFileSync, readdirSync, readFileSync, renameSync, rmSync } from 'node:fs';

import AxeBuilder from '@axe-core/playwright';
import { expect, test as base } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DATABASE, JOBS, PRISTINE, ROOT, SEED, TELEMETRY_OFF, python } from './stack/paths.mjs';

/** The English catalogue: tests find controls by the text people see. */
export const en = JSON.parse(readFileSync(new URL('../studio/src/i18n/en.json', import.meta.url), 'utf8'));

export interface EntityRef { type: string; id: string; version: string }
export interface Entity extends EntityRef { fields: Record<string, unknown> }

/** The part of `seed.json` (tests/seed.py) the tests use. */
export interface SeedManifest {
  authoring_context: string;
  delivery_context: string;
  pending_delivery_context: string;
  staff: string;
  project_id: string;
  project: EntityRef;
  pending_proposals: Record<string, EntityRef[]>;
}

export interface CliResult { status: number; output: unknown; errors: string }

const CONFIRM_PROMPT = 'Type CONFIRM: ';

/** The CLI on the database the API serves: what the browser did is checked there, or done "by another reviewer". */
export function cli(subject: string, context: string, args: string[], input = 'CONFIRM\n'): CliResult {
  const policy = 'architecture-policy-1.json';
  const run = spawnSync(python(), ['-m', 'learning', '--db', DATABASE, '--policy', `${SEED}policies/${policy}`,
    '--subject', subject, '--context', context, ...args], {
    cwd: ROOT, input, encoding: 'utf8', env: { ...process.env, ...TELEMETRY_OFF },
  });
  // `decide` prints the preview and the CONFIRM prompt before its result.
  const prompt = run.stdout.lastIndexOf(CONFIRM_PROMPT);
  const text = prompt >= 0 ? run.stdout.slice(prompt + CONFIRM_PROMPT.length) : run.stdout;
  let output: unknown;
  try {
    output = JSON.parse(text);
  } catch {
    output = text;
  }
  return { status: run.status ?? 1, output, errors: run.stderr };
}

/** The entities `show` lists for the staff subject. */
export function shown(context: string): Entity[] {
  const { status, output, errors } = cli('admin', context, ['show']);
  expect(status, errors).toBe(0);
  return (output as { entities: Entity[] }).entities;
}

export const test = base.extend<{ seed: SeedManifest }>({
  // Every test starts from the seed as built; the API opens the database per request.
  // The copy is renamed into place: a request still running from the previous test
  // would otherwise open a truncated file, which LearningStore initialises as new.
  seed: [async ({}, use) => {
    // Courses created by an earlier test lose their context with the restore: their policy files go too.
    for (const name of readdirSync(`${SEED}policies`)) {
      if (name.startsWith('course-')) rmSync(`${SEED}policies/${name}`);
    }
    copyFileSync(PRISTINE, `${DATABASE}.restore`);
    renameSync(`${DATABASE}.restore`, DATABASE);
    // The jobs of an earlier test go too. The worker keeps the jobs database open: its rows are deleted, the file stays.
    const cleared = spawnSync(python(), ['-c', 'import sqlite3, sys\nwith sqlite3.connect(sys.argv[1]) as db:\n'
      + '    db.execute("DELETE FROM events"); db.execute("DELETE FROM jobs")', JOBS], { encoding: 'utf8' });
    expect(cleared.status, cleared.stderr).toBe(0);
    await use(JSON.parse(readFileSync(`${SEED}seed.json`, 'utf8')) as SeedManifest);
  }, { auto: true }],
});

export { expect };

/** Create a course from the studio home page; it opens on its build page. */
export async function newCourse(page: Page, course: string) {
  await page.goto('/studio/');
  await page.getByLabel(en.home.courseLabel).fill(course);
  await page.getByRole('button', { name: en.home.create }).click();
  await expect(page).toHaveURL(`/studio/contexts/${course}/build`);
  await expect(page.getByRole('heading', { name: en.build.title, level: 1 })).toBeVisible();
}

/** Approve the proposal on screen with a reason, then apply it. */
export async function approveAndApply(page: Page) {
  await page.getByRole('radio', { name: en.review.decision.approve }).check();
  await page.getByLabel(en.review.decision.reason).fill('Synthetic review of the exact payload');
  await page.getByRole('button', { name: en.review.decision.submit }).click();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.approved);
  await page.getByRole('button', { name: en.review.apply.submit }).click();
  await expect(page.getByTestId('proposal-status')).toHaveText(en.review.status.applied);
}

/** WCAG 2.1 A and AA rules of axe on the current page; every violation fails the test. */
export async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.map(({ id, help, nodes }) => ({ id, help, targets: nodes.map((node) => node.target) })))
    .toEqual([]);
}
