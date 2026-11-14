import { copyFileSync, rmSync } from 'node:fs';
import { basename } from 'node:path';

import type { Page } from '@playwright/test';

import { SEED } from './stack/paths.mjs';
import { en, expect, expectAccessible, test } from './support';
import type { Entity } from './support';

const teacher = en.review.teacher;

/** The latest revision of every proposal of a context, read through the API with the browser's session. */
async function proposals(page: Page, context: string): Promise<Entity[]> {
  const response = await page.request.get(`/contexts/${context}`);
  expect(response.status(), await response.text()).toBe(200);
  const latest = new Map<string, Entity>();
  for (const entity of (await response.json() as { entities: Entity[] }).entities) {
    if (entity.type !== 'ChangeProposal') continue;
    const known = latest.get(entity.id);
    if (!known || Number(entity.version) > Number(known.version)) latest.set(entity.id, entity);
  }
  return [...latest.values()];
}

// Acceptance (S09c2 part 2, issue #121): every seeded proposal kind has a teacher view in words, whatever its
// status, and passes axe.
test('every proposal kind of the seed is read in words, whatever its status', async ({ page, seed }) => {
  const titles: string[] = [];
  const open = async (context: string, proposal: Entity) => {
    await page.goto(`/studio/contexts/${context}/review/${proposal.id}`);
    const title = page.locator('.alm-lead strong');
    await expect(title).not.toHaveText('');
    await expect(page.getByText(en.review.proposal.loadingContent)).toHaveCount(0);
    titles.push((await title.textContent()) ?? '');
    return (await title.textContent()) ?? '';
  };

  for (const proposal of await proposals(page, seed.authoring_context)) {
    const title = await open(seed.authoring_context, proposal);
    if (title === teacher.titleInitialization) {
      await expect(page.getByRole('region', { name: teacher.project.heading })).toContainText(
        `Approving creates the authoring project “${seed.project_id}”`);
      await expect(page.getByRole('region', { name: teacher.project.heading })).toContainText('Syllabus:');
    } else if (title === teacher.titleRelease) {
      await expect(page.getByRole('region', { name: teacher.release.heading })).toContainText(teacher.release.intro);
      await expect(page.getByTestId('course-parts')).toContainText('Assessments:');
    } else if (title === teacher.titleCompletion) {
      await expect(page.getByTestId('completion-rules')).toContainText('Complete this process node only when every direct child is COMPLETED.');
    } else if (title === teacher.titleTeacher || title === teacher.titleTrainer) {
      await expect(page.getByTestId('material').first()).toBeVisible();
    } else if (title === teacher.titleAssessment) {
      await expect(page.getByRole('region', { name: teacher.assessed.heading })).toBeVisible();
    }
    if (proposal.fields.status !== 'AWAITING_DECISION' && proposal.fields.status !== 'APPROVED') {
      // A decided proposal shows what it carries, not a comparison with the course as it is now.
      await expect(page.getByRole('region', { name: teacher.changes.heading })).toHaveCount(0);
    }
    await expectAccessible(page);
  }

  // The applied import gave its delivery context the policy of its preview: installing it is the operator's action
  // that makes the context available (D10). It is removed afterwards, so later tests see the seed as built.
  const installed = `${SEED}${seed.policy_dir}/${basename(seed.delivery_policy_preview)}`;
  copyFileSync(`${SEED}${seed.delivery_policy_preview}`, installed);
  try {
    for (const context of [seed.delivery_context, seed.pending_delivery_context]) {
      for (const proposal of (await proposals(page, context)).filter((p) => p.fields.status !== 'SUPERSEDED')) {
        if (await open(context, proposal) !== teacher.titleImport) continue;
        const delivery = page.getByRole('region', { name: teacher.delivery.heading });
        await expect(delivery).toContainText('Approving brings the frozen release into this delivery course');
        await expect(delivery).toContainText('Synthetic prompting guide');
        await expect(delivery).toContainText('guided-practice-coach');
        await expectAccessible(page);
      }
    }
  } finally {
    rmSync(installed, { force: true });
  }

  expect(new Set(titles)).toEqual(new Set([teacher.titleSyllabus, teacher.titleInitialization, teacher.titleAssessment,
    teacher.titleTeacher, teacher.titleTrainer, teacher.titleCompletion, teacher.titleRelease, teacher.titleImport]));
  expect(titles).not.toContain(teacher.titleOther);
});

test('the course page links every proposal, decided ones to be read', async ({ page, seed }) => {
  await page.goto(`/studio/contexts/${seed.authoring_context}/course`);
  await expect(page.getByRole('link', { name: en.course.history.review }).first()).toBeVisible();
  const read = page.getByRole('link', { name: en.course.history.read });
  await expect(read.first()).toBeVisible();
  await read.first().click();
  await expect(page).toHaveURL(new RegExp(`/studio/contexts/${seed.authoring_context}/review/`));
  await expect(page.locator('.alm-lead strong')).not.toHaveText(teacher.titleOther);
});
