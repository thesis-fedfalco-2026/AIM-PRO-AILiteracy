import { en, expect, expectAccessible, test } from './support';
import type { EntityRef } from './support';

// The marker makes the synthetic review agent refuse the first draft (tests/syllabus_fixtures.py).
const REQUIREMENT = 'Explain two prompting choices. [synthetic reviewer: reject the first draft]';

// Acceptance (S09c, D30 for the generators): the review agent's assessment of each draft of an Evaluator job,
// refused once and accepted on the next draft, read by the teacher in the job list as model text. The job writes
// its syllabus in blocks of units and the assembled draft is judged once more (S09d).
test("the review agent's assessment of each Evaluator draft is shown in the job list", async ({ page, seed }) => {
  const context = seed.authoring_context;
  await page.goto(`/studio/contexts/${context}/build`);
  await expect(page.getByTestId('course-jobs').or(page.getByText(en.build.jobs.none))).toBeVisible();
  // The studio has no Evaluator form before S09c2: the job is queued through the API with the browser's session.
  const session = await (await page.request.get('/auth/session')).json() as { csrf_token: string };
  const summary = await (await page.request.get(`/contexts/${context}`)).json() as { context: EntityRef };
  const { type, id, version } = summary.context;
  const queued = await page.request.post(`/contexts/${context}/jobs`, {
    headers: { 'X-CSRF-Token': session.csrf_token },
    data: { request_id: 'evaluator-reviewed', job: { kind: 'generate-project-assessments', command: {
      project: seed.project, base_context: { type, id, version }, requirements: [REQUIREMENT] } } },
  });
  expect(queued.status(), await queued.text()).toBe(200);

  const jobs = page.getByTestId('course-jobs');
  await expect(async () => {
    await page.getByRole('button', { name: en.build.jobs.reload }).click();
    await expect(jobs).toContainText(en.build.jobs.status.PROPOSED, { timeout: 1_000 });
  }).toPass({ timeout: 30_000 });
  await expect(jobs).toContainText('Blocks of units written: 1 of 1');
  await jobs.getByText(en.build.reviews.generation.summary).click();
  const attempts = page.getByTestId('review-attempts');
  await expect(attempts).toContainText(`Block 1, draft 1: ${en.build.reviews.outcome.rejected}`);
  await expect(attempts).toContainText('Content complete: no.');
  await expect(attempts).toContainText('(model text): “Synthetic refusal: the worksheet names a criterion it does not supply.”');
  await expect(attempts).toContainText(`Block 1, draft 2: ${en.build.reviews.outcome.accepted}`);
  await expect(attempts).toContainText(`The assembled draft of every block: ${en.build.reviews.outcome.accepted}`);
  // The review agent's text is never the job's detail.
  const view = await page.request.get(`/contexts/${context}/jobs/evaluator-reviewed`);
  expect(await view.text()).not.toContain('Synthetic refusal');
  await expectAccessible(page);
});
