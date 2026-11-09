import { spawnSync } from 'node:child_process';
import { copyFileSync, readdirSync, readFileSync } from 'node:fs';

import AxeBuilder from '@axe-core/playwright';
import { expect, test as base } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DATABASE, PRISTINE, ROOT, SEED, TELEMETRY_OFF, python } from './stack/paths.mjs';

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
  pending_proposals: Record<string, EntityRef[]>;
}

export interface CliResult { status: number; output: unknown; errors: string }

const CONFIRM_PROMPT = 'Type CONFIRM: ';

/** The CLI on the database the API serves: what the browser did is checked there, or done "by another reviewer". */
export function cli(subject: string, context: string, args: string[], input = 'CONFIRM\n'): CliResult {
  const [policy] = readdirSync(`${SEED}policies`).filter((name) => name.endsWith('.json'));
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
  seed: [async ({}, use) => {
    copyFileSync(PRISTINE, DATABASE);
    await use(JSON.parse(readFileSync(`${SEED}seed.json`, 'utf8')) as SeedManifest);
  }, { auto: true }],
});

export { expect };

/** WCAG 2.1 A and AA rules of axe on the current page; every violation fails the test. */
export async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.map(({ id, help, nodes }) => ({ id, help, targets: nodes.map((node) => node.target) })))
    .toEqual([]);
}
