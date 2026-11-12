import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { selectedProjects } from '../src/features/course-build/projects';
import { attemptOutcome } from '../src/features/course-build/ReviewAttempts';
import { rowProblem, sourcePlan } from '../src/features/course-build/SourcesStep';
import type { Entity } from '../src/features/review/reviewApi';
import en from '../src/i18n/en.json';
import type { Reply } from './harness';
import { renderStudio, SESSION } from './harness';

const provenance = { origin: 'GENERATED_PROPOSAL', responsible: 'admin', sources: [] };
const entity = (type: string, id: string, fields: Record<string, unknown>, version = 'v1') =>
  ({ type, id, version, fields, provenance });
const ref = (type: string, id: string, version = 'v1') => ({ type, id, version });

const signedIn: Reply = { status: 200, body: SESSION };
const EMPTY = entity('ExecutionContext', 'new-course', { status: 'DRAFT', mode: 'PREPARATION', models: [] }, '1');
const OUTLINE = ref('LearningDesign', 'outline');
const WITH_SYLLABUS = entity('ExecutionContext', 'new-course',
  { status: 'DRAFT', mode: 'PREPARATION', models: [], learningDesign: OUTLINE }, '3');
const summary = (context: unknown, entities: unknown[] = []): Reply =>
  ({ status: 200, body: { context, entities: [context, ...entities], findings: [] } });
const noPending: Reply = { status: 200, body: { proposals: [] } };
const page = (context: unknown, entities: unknown[] = []) => ({
  'GET /auth/session': [signedIn],
  'GET /contexts/new-course': [summary(context, entities)],
  'GET /contexts/new-course/pending-proposals': [noPending],
  'GET /contexts/new-course/jobs': [{ status: 200, body: { jobs: [] } }],
});

const EXPORT = { name: `${'a'.repeat(64)}.json`, sha256: 'a'.repeat(64) };
const REPORT = {
  export: EXPORT, size: 12, project_id: 'project-1', scenario: 'SCN01', competencies: 'elena_usecase_competencies',
  root_id: 'root-1', objects: 7, conforms: false,
  source_diagnostics: [{ code: 'CARDINALITY', object_id: 'o-1', object_name: 'Unit A', field: 'resources', count: 0, lower: 1 }],
  contract_findings: [{ code: 'GENERATED_CONTRACT', object_id: 'o-2', location: ['category'], message: 'Input should be Digital' }],
};
const job = (status: string, extra: Record<string, unknown> = {}) => ({
  context_id: 'new-course', request_id: 'request-1', subject_key: 'admin', status, proposal_refs: [], detail: null,
  created: 't', updated: 't',
  job: { kind: 'generate-aimpro-syllabus', project: EXPORT, source_scope: 'wp3', query: 'prompting', k: 5,
    scenario: 'SCN01', competencies: 'elena_usecase_competencies' },
  ...extra,
});

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

afterEach(cleanup);

describe('creating a course', () => {
  it('creates the course and opens its build page', async () => {
    const { requests, router } = await renderStudio({
      'GET /auth/session': [signedIn],
      'POST /courses': [{ status: 200, body: { context_id: 'new-course', policy_ref: ref('PolicySet', 'course:new-course', '1') } }],
      'GET /contexts/new-course': [summary(EMPTY)],
      'GET /contexts/new-course/pending-proposals': [noPending],
    });
    await screen.findByLabelText(en.home.courseLabel);
    fill(en.home.courseLabel, 'new-course');
    fireEvent.click(screen.getByRole('button', { name: en.home.create }));
    expect(await screen.findByRole('heading', { name: en.build.title, level: 1 })).toBeTruthy();
    expect(router.state.location.pathname).toBe('/studio/contexts/new-course/build');
    const post = requests.find((request) => request.method === 'POST')!;
    expect(post.headers.get('X-CSRF-Token')).toBe(SESSION.csrf_token);
    expect(await post.json()).toEqual({ context_id: 'new-course' });
  });

  it('checks the id before sending anything', async () => {
    const { requests } = await renderStudio({ 'GET /auth/session': [signedIn] });
    await screen.findByRole('button', { name: en.home.create });
    fireEvent.click(screen.getByRole('button', { name: en.home.create }));
    expect(screen.getByText(en.home.courseRequired)).toBeTruthy();
    fill(en.home.courseLabel, 'Not An Id');
    fireEvent.click(screen.getByRole('button', { name: en.home.create }));
    expect(screen.getByText(en.home.createInvalid)).toBeTruthy();
    expect(screen.getByLabelText(en.home.courseLabel).getAttribute('aria-invalid')).toBe('true');
    expect(requests.every((request) => request.method === 'GET')).toBe(true);
  });

  it('says who may create courses when the subject may not', async () => {
    await renderStudio({ 'GET /auth/session': [signedIn], 'POST /courses': [{ status: 403 }] });
    await screen.findByLabelText(en.home.courseLabel);
    fill(en.home.courseLabel, 'new-course');
    fireEvent.click(screen.getByRole('button', { name: en.home.create }));
    expect(await screen.findByText(en.home.createForbidden)).toBeTruthy();
  });
});

describe('building a course', () => {
  it('uploads the file as it is, shows its diagnostics in words and follows the Curator to its proposal', async () => {
    const { requests } = await renderStudio({
      ...page(EMPTY),
      'POST /contexts/new-course/aimpro-exports': [{ status: 200, body: REPORT }],
      'POST /contexts/new-course/jobs': [{ status: 200, body: job('QUEUED') }],
      'GET /contexts/new-course/jobs/request-1': [{ status: 200, body: job('RUNNING') }, {
        status: 200, body: job('PROPOSED', { proposal_refs: [ref('ChangeProposal', 'p-syllabus', '1')] }) }],
    }, '/studio/contexts/new-course/build');
    expect(await screen.findByText(en.build.curator.needsUpload)).toBeTruthy();
    expect(screen.getByText(en.build.project.needsSyllabus)).toBeTruthy();

    const bytes = '{"format": "jjodel-megamodel"}\r\n';
    fireEvent.change(screen.getByLabelText(en.build.upload.file), { target: { files: [new File([bytes], 'model.json')] } });
    fireEvent.click(screen.getByRole('button', { name: en.build.upload.submit }));
    expect(await screen.findByText(en.build.upload.stored)).toBeTruthy();
    const upload = requests.find((request) => request.method === 'POST')!;
    expect(new URL(upload.url).searchParams.get('scenario')).toBe('SCN01');
    expect(upload.headers.get('Content-Type')).toBe('application/octet-stream');
    expect(upload.headers.get('X-CSRF-Token')).toBe(SESSION.csrf_token);
    expect(await upload.text()).toBe(bytes);

    const report = within(screen.getByTestId('export-report'));
    expect(report.getByText('SCN01, 7 objects')).toBeTruthy();
    expect(report.getByText(en.build.upload.notConforms)).toBeTruthy();
    expect(report.getByText('“Unit A” has 0 resources; at least 1 is needed.')).toBeTruthy();
    expect(report.getByText('“o-2” does not fit the course model (category): Input should be Digital')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: en.build.curator.submit }));
    expect(screen.getByText(en.build.curator.scopeRequired)).toBeTruthy();
    fill(en.build.curator.scope, 'wp3');
    fill(en.build.curator.query, 'prompting');
    fireEvent.click(screen.getByRole('button', { name: en.build.curator.submit }));
    const link = await screen.findByRole('link', { name: en.build.curator.review });
    expect(link.getAttribute('href')).toBe('/studio/contexts/new-course/review/p-syllabus');
    expect(screen.getByText(en.build.curator.proposed)).toBeTruthy();
    const queued = requests.filter((request) => request.method === 'POST' && request.url.endsWith('/jobs'));
    expect(await queued[0]!.json()).toEqual({ request_id: 'request-1', job: job('QUEUED').job });
  });

  it('shows why a file is refused', async () => {
    await renderStudio({
      ...page(EMPTY),
      'POST /contexts/new-course/aimpro-exports': [{ status: 422, body: {
        error: 'validation', detail: 'The file is not UTF-8 JSON', request_id: 'r' } }],
    }, '/studio/contexts/new-course/build');
    fireEvent.change(await screen.findByLabelText(en.build.upload.file), { target: { files: [new File(['x'], 'x.json')] } });
    fireEvent.click(screen.getByRole('button', { name: en.build.upload.submit }));
    expect(await screen.findByText('Refused: The file is not UTF-8 JSON')).toBeTruthy();
    expect(screen.queryByTestId('export-report')).toBeNull();
    expect(screen.getByText(en.build.curator.needsUpload)).toBeTruthy();
  });

  it('says why the Curator ended without a proposal', async () => {
    await renderStudio({
      ...page(EMPTY),
      'POST /contexts/new-course/aimpro-exports': [{ status: 200, body: REPORT }],
      'POST /contexts/new-course/jobs': [{ status: 200, body: job('QUEUED') }],
      'GET /contexts/new-course/jobs/request-1': [{ status: 200, body: job('REJECTED', {
        detail: 'Syllabus corpus source scope is not authorized' }) }],
    }, '/studio/contexts/new-course/build');
    fireEvent.change(await screen.findByLabelText(en.build.upload.file), { target: { files: [new File(['{}'], 'm.json')] } });
    fireEvent.click(screen.getByRole('button', { name: en.build.upload.submit }));
    await screen.findByText(en.build.upload.stored);
    fill(en.build.curator.scope, 'other');
    fill(en.build.curator.query, 'prompting');
    fireEvent.click(screen.getByRole('button', { name: en.build.curator.submit }));
    expect(await screen.findByText('The Curator did not propose a syllabus: Syllabus corpus source scope is not authorized'))
      .toBeTruthy();
    expect(screen.getByText(en.build.curator.retry)).toBeTruthy();
  });

  it('proposes the project from the approved syllabus of the current outline', async () => {
    const syllabus = ref('Resource', 'outline:syllabus', '1');
    const { requests } = await renderStudio({
      ...page(WITH_SYLLABUS),
      'GET /contexts/new-course/designs/outline/versions/v1/syllabus': [{ status: 200, body: { syllabus } }],
      'POST /contexts/new-course/projects': [{ status: 200, body: {
        proposal: ref('ChangeProposal', 'p-project', '1'), project: ref('Resource', 'authoring-project:x'),
        domain: ref('DomainModel', 'authoring-project:x:model'), design: OUTLINE } }],
    }, '/studio/contexts/new-course/build');
    await screen.findByLabelText(en.build.project.label);
    fill(en.build.project.label, 'main');
    fireEvent.click(screen.getByRole('button', { name: en.build.project.submit }));
    const link = await screen.findByRole('link', { name: en.build.project.review });
    expect(link.getAttribute('href')).toBe('/studio/contexts/new-course/review/p-project');
    const post = requests.find((request) => request.method === 'POST')!;
    expect(await post.json()).toEqual({ request_id: 'request-1', project_id: 'main', syllabus,
      base_context: ref('ExecutionContext', 'new-course', '3') });
  });

  it('shows the initialized project instead of the form', async () => {
    const manifest = JSON.stringify({ format: 'authoring-project', project_id: 'main' });
    await renderStudio(page({ ...WITH_SYLLABUS, fields: { ...WITH_SYLLABUS.fields, models: [ref('DomainModel', 'p:model')] } }, [
      entity('DomainModel', 'p:model', { definitions: [ref('Resource', 'p')] }),
      entity('Resource', 'p', { contentOrLocator: manifest }),
    ]), '/studio/contexts/new-course/build');
    expect(await screen.findByText('Project “main” is initialized.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: en.build.project.submit })).toBeNull();
    expect(screen.getByText(en.build.project.next)).toBeTruthy();
  });

  it('names the current syllabus and says that a new one replaces it', async () => {
    await renderStudio(page(WITH_SYLLABUS, [entity('LearningDesign', 'outline', { name: 'Prompting basics' })]),
      '/studio/contexts/new-course/build');
    expect((await screen.findByText(en.build.current)).nextElementSibling?.textContent).toBe('Prompting basics');
    expect(screen.getByText(en.build.replaces)).toBeTruthy();
  });

  it('says that a course without a syllabus has none yet', async () => {
    await renderStudio(page(EMPTY), '/studio/contexts/new-course/build');
    expect((await screen.findByText(en.build.current)).nextElementSibling?.textContent).toBe(en.build.noSyllabus);
    expect(screen.queryByText(en.build.replaces)).toBeNull();
  });
});

const EXCERPT = {
  resource_id: 'wp3:test', resource_version: 'v1', document_id: 'chunk-1', content_sha256: 'c'.repeat(64),
  title: 'Synthetic prompting guide', uri: 'https://example.org/guide', licence: 'CC-BY-4.0', licence_verdict: null,
  text: 'Specify task, audience and tone.',
};
const QUERIES = [{ query: 'prompting', k: 10 }, { query: 'prompt clarity', k: 10 }];
const DISCOVERY_VIEW = { request_id: 'request-1', source_scope: 'wp3', queries: QUERIES,
  excerpts: [{ ...EXCERPT, found_by: ['prompting', 'prompt clarity'] }], unique_documents: 1, duplicate_hits: 1 };
const DOCUMENT = { resource_id: 'wp3:test', resource_version: 'v1', document_id: 'chunk-1', content_sha256: 'c'.repeat(64),
  purpose: 'Task, audience and tone.', limitations: ['Written for school teachers.', 'No assessment.'] };
const PLAN = { format: 'aimpro-source-plan', format_version: 1, source_sha256: EXPORT.sha256, source_scope: 'wp3',
  queries: QUERIES, documents: [DOCUMENT], min_resources: 1, max_documents_per_resource: 1, coverage_requirements: [] };
const PREPARATION_VIEW = { request_id: 'request-2', source_scope: 'wp3', source_sha256: EXPORT.sha256, queries: QUERIES,
  excerpts: [{ ...EXCERPT, licence_verdict: 'open', purpose: DOCUMENT.purpose, limitations: DOCUMENT.limitations }],
  coverage_requirements: [], min_resources: 1, max_documents_per_resource: 1, unique_documents: 1, duplicate_hits: 1 };
const sourceJob = (requestId: string, status: string, command: Record<string, unknown>) => ({
  ...job(status), request_id: requestId, job: command,
});
const discovery = (status: string) => sourceJob('request-1', status, { kind: 'discover-aimpro-syllabus-sources',
  discovery: { format: 'aimpro-source-discovery', format_version: 1, source_scope: 'wp3', queries: QUERIES } });
const preparation = (status: string) => sourceJob('request-2', status, { kind: 'prepare-aimpro-syllabus-sources',
  project: EXPORT, plan: PLAN, scenario: 'SCN01', competencies: 'elena_usecase_competencies' });
const curatorOnSources = sourceJob('request-3', 'QUEUED', { kind: 'generate-aimpro-syllabus', project: EXPORT,
  source_scope: 'wp3', prepared_sources: 'request-2', k: 5, scenario: 'SCN01', competencies: 'elena_usecase_competencies' });

describe('preparing the sources', () => {
  it('searches, picks an excerpt with its purpose and limitations, prepares it, accepts it and lets the Curator use it', async () => {
    const { requests } = await renderStudio({
      ...page(EMPTY),
      'POST /contexts/new-course/aimpro-exports': [{ status: 200, body: REPORT }],
      'POST /contexts/new-course/jobs': [{ status: 200, body: discovery('QUEUED') },
        { status: 200, body: preparation('QUEUED') }, { status: 200, body: curatorOnSources }],
      'GET /contexts/new-course/jobs/request-1': [{ status: 200, body: discovery('COMPLETED') }],
      'GET /contexts/new-course/source-discoveries/request-1': [{ status: 200, body: DISCOVERY_VIEW }],
      'GET /contexts/new-course/jobs/request-2': [{ status: 200, body: preparation('AWAITING_CHOICE') }],
      'GET /contexts/new-course/source-preparations/request-2': [{ status: 200, body: PREPARATION_VIEW }],
      'POST /contexts/new-course/jobs/request-2/choice': [{ status: 200, body: preparation('ACCEPTED') }],
      'GET /contexts/new-course/jobs/request-3': [{ status: 200, body: { ...curatorOnSources, status: 'RUNNING' } }],
    }, '/studio/contexts/new-course/build');
    expect(await screen.findByText(en.build.jobs.none)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(en.build.upload.file), { target: { files: [new File(['{}'], 'm.json')] } });
    fireEvent.click(screen.getByRole('button', { name: en.build.upload.submit }));
    await screen.findByText(en.build.upload.stored);

    fill(en.build.sources.scope, 'wp3');
    fill(en.build.sources.queries, 'prompting\nprompt clarity\n');
    fireEvent.click(screen.getByRole('button', { name: en.build.sources.search }));
    const excerpt = within(await screen.findByTestId('discovered-excerpt'));
    expect(excerpt.getByText('Found by: prompting, prompt clarity')).toBeTruthy();
    expect(excerpt.getByText('Usage conditions: licence CC-BY-4.0; the corpus has no verdict on it, check it before use.'))
      .toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: en.build.sources.prepare }));
    expect(screen.getByText(en.build.sources.pickOne)).toBeTruthy();
    fireEvent.click(excerpt.getByLabelText('Use excerpt 1'));
    fireEvent.click(screen.getByRole('button', { name: en.build.sources.prepare }));
    expect(screen.getByText(en.build.sources.purposeRequired)).toBeTruthy();
    fireEvent.change(excerpt.getByLabelText(en.build.sources.purpose), { target: { value: DOCUMENT.purpose } });
    fireEvent.change(excerpt.getByLabelText(en.build.sources.limitations),
      { target: { value: 'Written for school teachers.\n\nNo assessment.' } });
    fireEvent.click(screen.getByRole('button', { name: en.build.sources.prepare }));

    const prepared = within(await screen.findByTestId('prepared-sources'));
    expect(prepared.getByText('Usage conditions: licence CC-BY-4.0; the corpus verdict on it is “open”.')).toBeTruthy();
    expect(prepared.getByText('Written for school teachers.; No assessment.')).toBeTruthy();
    fireEvent.click(prepared.getByRole('button', { name: en.build.sources.accept }));
    expect(await screen.findByText(en.build.sources.accepted)).toBeTruthy();

    // The accepted sources are offered to the Curator, which needs no query for them.
    expect((screen.getByLabelText(en.build.curator.fromSources) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: en.build.curator.submit }));
    expect(await screen.findByText(en.build.curator.running)).toBeTruthy();

    const posted = requests.filter((request) => request.method === 'POST' && request.url.endsWith('/jobs'));
    expect(await posted[0]!.json()).toEqual({ request_id: 'request-1', job: discovery('QUEUED').job });
    expect(await posted[1]!.json()).toEqual({ request_id: 'request-2', job: preparation('QUEUED').job });
    expect(await posted[2]!.json()).toEqual({ request_id: 'request-3', job: curatorOnSources.job });
    const choice = requests.find((request) => request.url.endsWith('/choice'))!;
    expect(choice.headers.get('X-CSRF-Token')).toBe(SESSION.csrf_token);
    expect(await choice.json()).toEqual({ choice: 'ACCEPTED' });
  });

  it('resumes a preparation awaiting the choice from the list of jobs, and declines it', async () => {
    const { requests } = await renderStudio({
      ...page(EMPTY),
      'GET /contexts/new-course/jobs': [{ status: 200, body: { jobs: [preparation('AWAITING_CHOICE'), discovery('COMPLETED')] } }],
      'GET /contexts/new-course/source-preparations/request-2': [{ status: 200, body: PREPARATION_VIEW }],
      'POST /contexts/new-course/jobs/request-2/choice': [{ status: 200, body: preparation('DECLINED') }],
    }, '/studio/contexts/new-course/build');
    const list = within(await screen.findByTestId('course-jobs'));
    expect(list.getByText(/Preparation of the sources: waiting for your choice/)).toBeTruthy();
    expect(list.getByText(/Search of the sources: done/)).toBeTruthy();
    fireEvent.click(list.getByRole('button', { name: en.build.jobs.choose }));
    const prepared = within(await screen.findByTestId('prepared-sources'));
    fireEvent.click(prepared.getByRole('button', { name: en.build.sources.decline }));
    expect(await screen.findByText(en.build.sources.declined)).toBeTruthy();
    expect(await requests.find((request) => request.url.endsWith('/choice'))!.json()).toEqual({ choice: 'DECLINED' });
    // Nothing was accepted: the Curator offers no prepared sources.
    expect(screen.queryByLabelText(en.build.curator.fromSources)).toBeNull();
  });

  it('builds the plan from the picked excerpts and checks each quoted passage', () => {
    const choices = { 'chunk-1': { picked: true, purpose: ' Task. ', limitations: 'One\n\n two ' } };
    expect(sourcePlan(DISCOVERY_VIEW as never, EXPORT.sha256, choices, [])).toEqual({
      ...PLAN, documents: [{ ...DOCUMENT, purpose: 'Task.', limitations: ['One', 'two'] }] });
    const targets = { export: EXPORT, scenario: 'SCN01', competencies: 'c', root_id: 'r', targets: [{
      id: 't', class_name: 'LearningTarget', fields: { description: 'Write a first prompt.' },
      practices: [{ id: 'p', class_name: 'Practice', fields: { inPractice: 'Builds a reminder prompt live.' } }] }] };
    const row = { target: 't', object: 'p', field: 'inPractice', quote: 'reminder prompt', actor: 'LEARNER' as const,
      intent: 'PRACTICE' as const, action: 'Build one' };
    expect(rowProblem(targets, row)).toBeNull();
    expect(rowProblem(targets, { ...row, quote: 'invented text' })).toBe('quote');
    expect(rowProblem(targets, { ...row, action: ' ' })).toBe('missing');
  });
});

describe('a course without a syllabus', () => {
  it('links its course page to the build page for its author', async () => {
    const author = entity('Participant', 'new-course:participant:admin', { subjectKey: 'admin', roles: ['ADMINISTRATOR'] });
    await renderStudio(page(EMPTY, [author]), '/studio/contexts/new-course/course');
    expect(await screen.findByText(en.course.notStarted)).toBeTruthy();
    expect(screen.getByRole('link', { name: en.course.build }).getAttribute('href')).toBe('/studio/contexts/new-course/build');
  });
});

describe('a context without a design', () => {
  it('is not visible to a subject who is not its author', async () => {
    const learner = entity('Participant', 'new-course:participant:admin', { subjectKey: 'admin', roles: ['LEARNER'] });
    await renderStudio(page(EMPTY, [learner]), '/studio/contexts/new-course/course');
    expect(await screen.findByText(en.course.notVisible)).toBeTruthy();
    expect(screen.queryByRole('link', { name: en.course.build })).toBeNull();
  });
});

describe('selected projects', () => {
  it('are the project manifests of the context models only', () => {
    const manifest = (id: string) => JSON.stringify({ format: 'authoring-project', project_id: id });
    const context = entity('ExecutionContext', 'c', { models: [ref('DomainModel', 'm')] });
    const entities = [
      context,
      entity('DomainModel', 'm', { definitions: [ref('Resource', 'a'), ref('Resource', 'text')] }),
      entity('DomainModel', 'proposed', { definitions: [ref('Resource', 'b')] }),
      entity('Resource', 'a', { contentOrLocator: manifest('main') }),
      entity('Resource', 'b', { contentOrLocator: manifest('pending') }),
      entity('Resource', 'text', { contentOrLocator: '{not json' }),
    ];
    expect(selectedProjects(context as Entity, entities as Entity[])).toEqual(['main']);
  });
});


describe('the review agent on the Curator drafts (Chat 20)', () => {
  const verdict = (changes: Record<string, unknown> = {}) => ({
    verdict: 'ACCEPT', source_alignment: true, citation_support: true, reason: 'Aligned and supported.', ...changes });
  const REJECTED = verdict({ verdict: 'REJECT', citation_support: false, reason: 'The excerpt does not support the claim.' });
  const REVIEWS = { request_id: 'request-1', outcome: 'FAILURE', attempts: [
    { attempt: 1, review: null, check: 'Syllabus unit practices are outside its source target' },
    { attempt: 2, review: REJECTED, check: null },
    { attempt: 3, review: verdict({ verdict: 'UNCERTAIN', reason: 'Unsure.' }), check: null }] };
  const toggle = (details: HTMLElement) => {
    (details as HTMLDetailsElement).open = true;
    fireEvent(details, new Event('toggle'));
  };

  it('names how each draft ended', () => {
    expect(REVIEWS.attempts.map((attempt) => attemptOutcome(attempt as never))).toEqual(['checks', 'rejected', 'uncertain']);
    expect(attemptOutcome({ attempt: 1, review: verdict(), check: null } as never)).toBe('accepted');
    expect(attemptOutcome({ attempt: 1, review: verdict({ source_alignment: false }), check: null } as never)).toBe('rejected');
  });

  it('shows the assessments of an ended Curator job when the teacher opens them, as model text', async () => {
    const failed = job('FAILED', { detail: 'Syllabus generation did not complete (Syllabus did not pass semantic review); no proposal was applied.' });
    const other = job('FAILED', { request_id: 'request-2', subject_key: 'someone-else' });
    const { requests } = await renderStudio({
      ...page(EMPTY),
      'GET /contexts/new-course/jobs': [{ status: 200, body: { jobs: [failed, other, job('RUNNING', { request_id: 'request-3' })] } }],
      'GET /contexts/new-course/syllabus-reviews/request-1': [{ status: 200, body: REVIEWS }],
    }, '/studio/contexts/new-course/build');
    const list = within(await screen.findByTestId('course-jobs'));
    // Only the teacher's own ended job offers them, and nothing is read before they are opened.
    const summaries = list.getAllByText(en.build.reviews.summary);
    expect(summaries).toHaveLength(1);
    expect(requests.some((request) => request.url.includes('syllabus-reviews'))).toBe(false);
    toggle(summaries[0]!.closest('details')!);
    const attempts = within(await screen.findByTestId('review-attempts'));
    expect(attempts.getByText(`Draft 1: ${en.build.reviews.outcome.checks}`)).toBeTruthy();
    expect(attempts.getByText('Reason: Syllabus unit practices are outside its source target')).toBeTruthy();
    expect(attempts.getByText(`Draft 2: ${en.build.reviews.outcome.rejected}`)).toBeTruthy();
    expect(attempts.getByText('Fits the course model and its sources: yes. Citations support the claims: no.')).toBeTruthy();
    expect(attempts.getByText("The review agent's assessment (model text): \u201cThe excerpt does not support the claim.\u201d")).toBeTruthy();
    expect(attempts.getByText(`Draft 3: ${en.build.reviews.outcome.uncertain}`)).toBeTruthy();
  });
});

describe('the review agent on the Evaluator, Teacher and Trainer drafts (S09c)', () => {
  const verdict = (changes: Record<string, unknown> = {}) => ({ verdict: 'ACCEPT', source_alignment: true,
    citation_support: true, intent_correct: true, content_complete: true, reason: 'Complete and supported.', ...changes });
  const command = { project: { type: 'Resource', id: 'project', version: '1' },
    base_context: { type: 'ExecutionContext', id: 'new-course', version: '3' } };
  const generator = (kind: string, extra: Record<string, unknown> = {}) =>
    job('PROPOSED', { job: { kind, command }, ...extra });
  const REVIEWS = { request_id: 'request-1', outcome: 'PROPOSAL', attempts: [
    { attempt: 1, review: verdict({ verdict: 'REJECT', content_complete: false, reason: 'The worksheet lacks its criterion.' }),
      check: null },
    { attempt: 2, review: verdict(), check: null }] };

  it('names a draft not accepted when any of the four checks failed', () => {
    expect(REVIEWS.attempts.map((attempt) => attemptOutcome(attempt as never))).toEqual(['rejected', 'accepted']);
    expect(attemptOutcome({ attempt: 1, review: verdict({ intent_correct: false }), check: null } as never)).toBe('rejected');
  });

  it('shows the assessments of an ended generator job when the teacher opens them, as model text', async () => {
    const { requests } = await renderStudio({
      ...page(EMPTY),
      'GET /contexts/new-course/jobs': [{ status: 200, body: { jobs: [
        generator('generate-project-trainer'),
        generator('generate-project-teacher', { request_id: 'request-2', status: 'RUNNING' }),
        generator('generate-project-assessments', { request_id: 'request-3', subject_key: 'someone-else' })] } }],
      'GET /contexts/new-course/generation-reviews/request-1': [{ status: 200, body: REVIEWS }],
    }, '/studio/contexts/new-course/build');
    const list = within(await screen.findByTestId('course-jobs'));
    // Only the teacher's own ended job offers them, and nothing is read before they are opened.
    const summaries = list.getAllByText(en.build.reviews.generation.summary);
    expect(summaries).toHaveLength(1);
    expect(list.queryByText(en.build.reviews.summary)).toBeNull();
    expect(requests.some((request) => request.url.includes('generation-reviews'))).toBe(false);
    const details = summaries[0]!.closest('details')! as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event('toggle'));
    const attempts = within(await screen.findByTestId('review-attempts'));
    expect(attempts.getByText(`Draft 1: ${en.build.reviews.outcome.rejected}`)).toBeTruthy();
    expect(attempts.getByText('Fits the approved syllabus and its sources: yes. Citations support the claims: yes. '
      + 'Right intent (explain, practice or assess): yes. Content complete: no.')).toBeTruthy();
    expect(attempts.getByText("The review agent's assessment (model text): “The worksheet lacks its criterion.”")).toBeTruthy();
    expect(attempts.getByText(`Draft 2: ${en.build.reviews.outcome.accepted}`)).toBeTruthy();
    expect(requests.some((request) => request.url.includes('syllabus-reviews'))).toBe(false);
  });

  it('shows the blocks of units a job has written and the draft of each block (S09d)', async () => {
    const blocks = { request_id: 'request-1', outcome: 'FAILURE', attempts: [
      { attempt: 1, block: 1, reused: true, review: verdict(), check: null },
      { attempt: 1, block: 2, review: verdict({ verdict: 'REJECT', content_complete: false, reason: 'Unit 14 lacks a rubric.' }),
        check: null },
      { attempt: 2, block: 2, review: verdict(), check: null },
      { attempt: 1, final: true, review: verdict({ verdict: 'UNCERTAIN', reason: 'Units repeat across blocks.' }), check: null }] };
    await renderStudio({
      ...page(EMPTY),
      'GET /contexts/new-course/jobs': [{ status: 200, body: { jobs: [
        generator('generate-project-assessments', { status: 'FAILED', blocks: { written: 2, count: 4 } })] } }],
      'GET /contexts/new-course/generation-reviews/request-1': [{ status: 200, body: blocks }],
    }, '/studio/contexts/new-course/build');
    const list = within(await screen.findByTestId('course-jobs'));
    expect(list.getByText('Blocks of units written: 2 of 4')).toBeTruthy();
    const details = list.getByText(en.build.reviews.generation.summary).closest('details')! as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event('toggle'));
    const attempts = within(await screen.findByTestId('review-attempts'));
    expect(attempts.getByText('Block 1: accepted in an earlier job over the same inputs, used again without a new draft'))
      .toBeTruthy();
    expect(attempts.getByText(`Block 2, draft 1: ${en.build.reviews.outcome.rejected}`)).toBeTruthy();
    expect(attempts.getByText(`Block 2, draft 2: ${en.build.reviews.outcome.accepted}`)).toBeTruthy();
    expect(attempts.getByText(`The assembled draft of every block: ${en.build.reviews.outcome.uncertain}`)).toBeTruthy();
    expect(attempts.getByText("The review agent's assessment (model text): “Units repeat across blocks.”")).toBeTruthy();
  });
});

describe('the Evaluator, Teacher and Trainer forms and the completion rules (S09c2)', () => {
  const manifest = JSON.stringify({ format: 'authoring-project', project_id: 'main' });
  const context = (version: string) => entity('ExecutionContext', 'new-course',
    { status: 'DRAFT', mode: 'PREPARATION', models: [ref('DomainModel', 'p:model')], learningDesign: OUTLINE }, version);
  const records = [entity('DomainModel', 'p:model', { definitions: [ref('Resource', 'p')] }),
    entity('Resource', 'p', { contentOrLocator: manifest })];
  const PROJECT = ref('Resource', 'authoring-project:main', '7');
  const ASSESSMENT = ref('Resource', 'assessment-package', '2');
  const artifact = (kind: string, resource: unknown) => ({ key: kind.toLowerCase(), kind, resource, depends_on: [], definitions: [] });
  const inspection = (artifacts: unknown[], stale: unknown[] = []): Reply => ({ status: 200, body: {
    project: PROJECT, manifest: { artifacts }, artifacts: [], stale_dependencies: stale } });
  /** The build page (inbox, jobs) and the forms (inbox again, project inspection), read once each. */
  const opened = (version: string, project: Reply) => ({
    'GET /auth/session': [signedIn],
    'GET /contexts/new-course': [summary(context(version), records), summary(context(version), records)],
    'GET /contexts/new-course/pending-proposals': [noPending, noPending],
    'GET /contexts/new-course/jobs': [{ status: 200, body: { jobs: [] } }],
    'GET /contexts/new-course/projects/main': [project],
  });
  const section = async (name: string) => within(await screen.findByRole('region', { name }));
  const heading = (role: 'evaluator' | 'teacher' | 'trainer', step: number) =>
    en.build.generators[role].heading.replace('{{step}}', String(step));

  it('shows the exact refs each form sends and queues the Evaluator with them', async () => {
    const queued = job('QUEUED', { job: { kind: 'generate-project-assessments', command: {} } });
    const { requests } = await renderStudio({
      ...opened('5', inspection([artifact('SYLLABUS', ref('Resource', 'syllabus'))])),
      'POST /contexts/new-course/jobs': [{ status: 200, body: queued }],
      'GET /contexts/new-course/jobs/request-1': [{ status: 200, body: { ...queued, status: 'PROPOSED',
        proposal_refs: [ref('ChangeProposal', 'p-assessments', '1')] } }],
    }, '/studio/contexts/new-course/build');
    const evaluator = await section(heading('evaluator', 5));
    const refs = within(evaluator.getByTestId('sent-refs'));
    expect(refs.getByText('authoring-project:main').parentElement?.textContent).toBe('authoring-project:main (version 7)');
    expect(refs.getByText('new-course').parentElement?.textContent).toBe('new-course (version 5)');
    // The Teacher and Trainer build on the applied assessments: none yet.
    for (const role of ['teacher', 'trainer'] as const) {
      const form = await section(heading(role, role === 'teacher' ? 6 : 7));
      expect(form.getByText(en.build.generators.noAssessments)).toBeTruthy();
      expect(form.getByText(en.build.generators.needsAssessments)).toBeTruthy();
      expect(form.queryByRole('button')).toBeNull();
    }
    expect((await section(en.build.completion.heading)).getByText(en.build.completion.needsTrainer)).toBeTruthy();

    fireEvent.change(evaluator.getByLabelText(en.build.generators.requirements), { target: { value: 'Explain two choices.\n\n' } });
    fireEvent.click(evaluator.getByRole('button', { name: en.build.generators.evaluator.submit }));
    const link = await evaluator.findByRole('link', { name: en.build.generators.review });
    expect(link.getAttribute('href')).toBe('/studio/contexts/new-course/review/p-assessments');
    const post = requests.find((request) => request.method === 'POST')!;
    expect(post.headers.get('X-CSRF-Token')).toBe(SESSION.csrf_token);
    expect(await post.json()).toEqual({ request_id: 'request-1', job: { kind: 'generate-project-assessments', command: {
      project: PROJECT, base_context: ref('ExecutionContext', 'new-course', '5'), assessments: [],
      requirements: ['Explain two choices.'], shared_content: [], stimulus_requirements: [] } } });
  });

  it('reads the form again when the course has changed since it was read, and queues on the new base', async () => {
    const replies = opened('5', inspection([artifact('ASSESSMENT', ASSESSMENT)]));
    const queued = job('QUEUED', { request_id: 'request-2', job: { kind: 'generate-project-teacher', command: {} } });
    const { requests } = await renderStudio({
      ...replies,
      'GET /contexts/new-course': [...replies['GET /contexts/new-course'], summary(context('6'), records)],
      'GET /contexts/new-course/pending-proposals': [noPending, noPending, noPending],
      'GET /contexts/new-course/projects/main': [...replies['GET /contexts/new-course/projects/main'],
        inspection([artifact('ASSESSMENT', ASSESSMENT)])],
      'POST /contexts/new-course/jobs': [
        { status: 409, body: { error: 'conflict', detail: 'The course has changed since this form was read; reload it', request_id: 'r' } },
        { status: 200, body: queued }],
      'GET /contexts/new-course/jobs/request-2': [{ status: 200, body: { ...queued, status: 'RUNNING' } }],
    }, '/studio/contexts/new-course/build');
    const teacher = await section(heading('teacher', 6));
    expect(within(teacher.getByTestId('sent-refs')).getByText('assessment-package').parentElement?.textContent)
      .toBe('assessment-package (version 2)');
    fireEvent.click(teacher.getByRole('button', { name: en.build.generators.teacher.submit }));
    expect(await teacher.findByText(en.build.generators.stale)).toBeTruthy();
    await waitFor(() => expect(within(teacher.getByTestId('sent-refs')).getByText('new-course').parentElement?.textContent)
      .toBe('new-course (version 6)'));
    fireEvent.click(teacher.getByRole('button', { name: en.build.generators.teacher.submit }));
    expect(await teacher.findByText(en.build.generators.running)).toBeTruthy();
    const posts = await Promise.all(requests.filter((request) => request.method === 'POST').map((request) => request.json()));
    expect(posts.map((body) => [body.request_id, body.job.command.base_context.version, body.job.command.assessments]))
      .toEqual([['request-1', '5', [ASSESSMENT]], ['request-2', '6', [ASSESSMENT]]]);
  });

  it('proposes the completion rules on the exact project and course version', async () => {
    const { requests } = await renderStudio({
      ...opened('9', inspection([artifact('ASSESSMENT', ASSESSMENT), artifact('TRAINER_CONTENT', ref('Resource', 'trainer'))])),
      'POST /contexts/new-course/completion-rules': [{ status: 200, body: {
        proposal: ref('ChangeProposal', 'p-rules', '1'), project: PROJECT, domain: ref('DomainModel', 'd'), design: OUTLINE } }],
    }, '/studio/contexts/new-course/build');
    const completion = await section(en.build.completion.heading);
    fireEvent.click(completion.getByRole('button', { name: en.build.completion.submit }));
    const link = await completion.findByRole('link', { name: en.build.completion.review });
    expect(link.getAttribute('href')).toBe('/studio/contexts/new-course/review/p-rules');
    const post = requests.find((request) => request.method === 'POST')!;
    expect(await post.json()).toEqual({ request_id: 'request-1', project: PROJECT,
      base_context: ref('ExecutionContext', 'new-course', '9') });
  });

  it('asks for content made from an earlier version to be generated again before the rules', async () => {
    await renderStudio(opened('9', inspection([artifact('TRAINER_CONTENT', ref('Resource', 'trainer'))],
      [{ code: 'STALE_DEPENDENCY', target: 'trainer_content', reason: 'r', resolution: 's' }])), '/studio/contexts/new-course/build');
    const completion = await section(en.build.completion.heading);
    expect(completion.getByText(en.build.completion.needsFresh)).toBeTruthy();
    expect(completion.queryByRole('button')).toBeNull();
    expect(screen.getByText(en.build.generators.staleContent.replace('{{targets}}', 'Trainer content'))).toBeTruthy();
  });
});
