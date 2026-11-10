import { cleanup, fireEvent, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { selectedProjects } from '../src/features/course-build/projects';
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
    const queued = requests.filter((request) => request.url.endsWith('/jobs'));
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

