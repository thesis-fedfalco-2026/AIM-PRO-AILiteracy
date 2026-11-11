import type { Page } from '@playwright/test';

import { AIMPRO_EXPORT } from './stack/paths.mjs';
import { approveAndApply, en, expect, expectAccessible, newCourse, test } from './support';
import type { Entity, EntityRef } from './support';

const COURSE = 'prompting-cycle';
const BUILD = `/studio/contexts/${COURSE}/build`;

const heading = (role: 'evaluator' | 'teacher' | 'trainer', step: number) =>
  en.build.generators[role].heading.replace('{{step}}', String(step));
const section = (page: Page, name: string) => page.getByRole('region', { name });

interface Inspection {
  project: EntityRef;
  manifest: { design: EntityRef; artifacts: { kind: string; resource: EntityRef }[] };
  artifacts: { receipt: unknown; approval_error: string | null }[];
  stale_dependencies: unknown[];
}

async function courseVersion(page: Page): Promise<string> {
  return ((await (await page.request.get(`/contexts/${COURSE}`)).json()) as { context: EntityRef }).context.version;
}

async function inspection(page: Page): Promise<Inspection> {
  return (await page.request.get(`/contexts/${COURSE}/projects/main`)).json() as Promise<Inspection>;
}

/** Upload the model, let the Curator draft the syllabus, apply it, then initialize and apply the project. */
async function initializedCourse(page: Page) {
  await newCourse(page, COURSE);
  await page.getByLabel(en.build.upload.file).setInputFiles(AIMPRO_EXPORT);
  await page.getByRole('button', { name: en.build.upload.submit }).click();
  await expect(page.getByText(en.build.upload.stored)).toBeVisible();
  await page.getByLabel(en.build.curator.scope, { exact: true }).fill('wp3');
  await page.getByLabel(en.build.curator.query).fill('prompting');
  await page.getByRole('button', { name: en.build.curator.submit }).click();
  await page.getByRole('link', { name: en.build.curator.review }).click({ timeout: 30_000 });
  await approveAndApply(page);
  await page.goto(BUILD);
  await page.getByLabel(en.build.project.label).fill('main');
  await page.getByRole('button', { name: en.build.project.submit }).click();
  await page.getByRole('link', { name: en.build.project.review }).click();
  await approveAndApply(page);
}

/** Queue a generator from its form, open its proposal, read it in its teacher view (axe), approve and apply it. */
async function generate(page: Page, form: string, submit: string, title: string) {
  await page.goto(BUILD);
  const step = section(page, form);
  await step.getByRole('button', { name: submit }).click();
  await step.getByRole('link', { name: en.build.generators.review }).click({ timeout: 30_000 });
  await expect(page.getByText(title, { exact: true })).toBeVisible();
  await expectAccessible(page);
}

/** The process nodes of the course's current design without a completion rule. */
async function nodesWithoutRule(page: Page, design: EntityRef): Promise<string[]> {
  const { entities } = await (await page.request.get(`/contexts/${COURSE}`)).json() as { entities: Entity[] };
  const find = (ref: EntityRef) => entities.find((e) => e.type === ref.type && e.id === ref.id && e.version === ref.version)!;
  const missing: string[] = [];
  const visit = (node: Entity) => {
    if (!node.fields.completionRule) missing.push(node.id);
    (node.fields.children as EntityRef[]).forEach((child) => visit(find(child)));
  };
  visit(find(find(design).fields.root as EntityRef));
  return missing;
}

// Acceptance (S09c2): from the studio the author queues the Evaluator, Teacher and Trainer from their forms, reads
// each proposal in its teacher view, approves and applies it, then proposes and applies the completion rules; the
// project ends in the state of build_project() (tests/test_authoring_cycle.py). A stale form is refused and read again.
test('the rest of the authoring cycle runs from the studio', async ({ page }) => {
  test.setTimeout(180_000);
  await initializedCourse(page);

  // The form shows the exact refs it sends.
  await page.goto(BUILD);
  const evaluator = section(page, heading('evaluator', 5));
  const project = await inspection(page);
  const before = await courseVersion(page);
  const refs = evaluator.getByTestId('sent-refs');
  await expect(refs).toContainText(`${project.project.id} (version ${project.project.version})`);
  await expect(refs).toContainText(`${COURSE} (version ${before})`);
  await expect(section(page, heading('teacher', 6))).toContainText(en.build.generators.needsAssessments);
  await expectAccessible(page);

  // The course changes while the form is open: another author applies an Evaluator proposal through the API.
  // The form's job is then refused at queue time (409) and the form reads the course again.
  const session = await (await page.request.get('/auth/session')).json() as { csrf_token: string };
  const write = async (path: string, data: unknown) => {
    const response = await page.request.post(`/contexts/${COURSE}/${path}`, { headers: { 'X-CSRF-Token': session.csrf_token }, data });
    expect(response.status(), await response.text()).toBe(200);
    return response.json();
  };
  await write('jobs', { request_id: 'other-author', job: { kind: 'generate-project-assessments', command: {
    project: project.project, base_context: { type: 'ExecutionContext', id: COURSE, version: before } } } });
  let other: EntityRef | undefined;
  await expect(async () => {
    const job = await (await page.request.get(`/contexts/${COURSE}/jobs/other-author`)).json() as { proposal_refs: EntityRef[] };
    other = job.proposal_refs[0];
    expect(other).toBeDefined();
  }).toPass({ timeout: 30_000 });
  const { proposals } = await (await page.request.get(`/contexts/${COURSE}/pending-proposals`)).json() as {
    proposals: { proposal: Entity; review_payload_key: string }[] };
  const key = proposals.find((item) => item.proposal.id === other!.id)!.review_payload_key;
  await write('decisions', { target: other, decision: 'APPROVE', reason: 'Another author applies a draft', review_payload_key: key });
  await write('applications', { proposal: other, operation_id: 'other-author' });
  const after = await courseVersion(page);
  expect(after).not.toBe(before);
  await evaluator.getByRole('button', { name: en.build.generators.evaluator.submit }).click();
  await expect(evaluator).toContainText(en.build.generators.stale);
  await expect(refs).toContainText(`${COURSE} (version ${after})`);

  // Evaluator, Teacher and Trainer, each read in its teacher view, approved and applied.
  await evaluator.getByRole('button', { name: en.build.generators.evaluator.submit }).click();
  await evaluator.getByRole('link', { name: en.build.generators.review }).click({ timeout: 30_000 });
  await expect(page.getByText(en.review.teacher.titleAssessment, { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: en.review.teacher.assessed.heading })).toBeVisible();
  await expectAccessible(page);
  await approveAndApply(page);

  await page.goto(BUILD);
  const assessment = (await inspection(page)).manifest.artifacts.find((a) => a.kind === 'ASSESSMENT')!.resource;
  await expect(section(page, heading('teacher', 6)).getByTestId('sent-refs'))
    .toContainText(`${assessment.id} (version ${assessment.version})`);
  await generate(page, heading('teacher', 6), en.build.generators.teacher.submit, en.review.teacher.titleTeacher);
  await expect(page.getByRole('heading', { name: en.review.teacher.materials.heading })).toBeVisible();
  await expect(page.getByTestId('material').first()).toContainText('Synthetic');
  await approveAndApply(page);

  await generate(page, heading('trainer', 7), en.build.generators.trainer.submit, en.review.teacher.titleTrainer);
  await expect(page.getByTestId('material').first()).toContainText('Synthetic WORKSHEET');
  await approveAndApply(page);

  // The completion rules: proposed from the studio, read part by part, approved and applied.
  await page.goto(BUILD);
  const completion = section(page, en.build.completion.heading);
  await completion.getByRole('button', { name: en.build.completion.submit }).click();
  await completion.getByRole('link', { name: en.build.completion.review }).click();
  await expect(page.getByText(en.review.teacher.titleCompletion, { exact: true })).toBeVisible();
  await expect(page.getByTestId('completion-rules').getByRole('listitem').first()).toContainText('every direct child is COMPLETED');
  await expectAccessible(page);
  await approveAndApply(page);

  // The state of build_project(): every artifact selected and approved, no stale dependency, a rule on every node.
  const done = await inspection(page);
  expect(done.manifest.artifacts.map((a) => a.kind)).toEqual(['SOURCE', 'SYLLABUS', 'ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT']);
  expect(done.artifacts.every((a) => a.receipt !== null && a.approval_error === null)).toBe(true);
  expect(done.stale_dependencies).toEqual([]);
  expect(await nodesWithoutRule(page, done.manifest.design)).toEqual([]);
});
