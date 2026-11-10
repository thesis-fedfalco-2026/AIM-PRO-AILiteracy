import { Button, StatusMessage } from '@alm/ui';
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { refOf } from '../review/model';
import { LoadFailure } from '../review/parts';
import { coursePath, inboxPath, proposalPath } from '../review/paths';
import type { EntityRef, Inbox, JsonValue } from '../review/reviewApi';
import { useCsrfToken } from '../review/ReviewServices';
import { plainIssues } from '../review/teacher';
import { IssueText } from '../review/TeacherView';
import { useInbox } from '../review/useInbox';
import { ENDED_STATUSES, PREPARATION } from './buildApi';
import type { ExportReport, JobView } from './buildApi';
import { useBuildServices } from './BuildServices';
import { JobsList } from './JobsList';
import { describedBy, Field, TextInput, useFollowedJob, useStep, useSubjectKey } from './parts';
import { currentDesign, designName, selectedProjects } from './projects';
import { SourcesStep } from './SourcesStep';

function Report({ report }: { report: ExportReport }) {
  const { t } = useTranslation();
  // The API sends JSON: the diagnostics are JSON values.
  const diagnostics = { source_diagnostics: report.source_diagnostics, contract_findings: report.contract_findings };
  const issues = plainIssues(diagnostics as unknown as Record<string, JsonValue>, [], []);
  return (
    <div data-testid="export-report">
      <dl className="alm-facts">
        <dt>{t('build.upload.project')}</dt>
        <dd>{report.project_id}</dd>
        <dt>{t('build.upload.scenario')}</dt>
        <dd>{t('build.upload.scenarioValue', { scenario: report.scenario, objects: String(report.objects) })}</dd>
        <dt>{t('build.upload.digest')}</dt>
        <dd><code>{report.export.sha256}</code></dd>
      </dl>
      <p>{report.conforms ? t('build.upload.conforms') : t('build.upload.notConforms')}</p>
      {issues.generated.length > 0 ? (
        <details className="alm-disclosure">
          <summary>{t('build.upload.contractIssues', { found: String(issues.generated.length) })}</summary>
          <ul>{issues.generated.map((issue, index) => <li key={index}><IssueText issue={issue} /></li>)}</ul>
        </details>
      ) : null}
      {issues.source.length > 0 ? (
        <details className="alm-disclosure">
          <summary>{t('build.upload.sourceIssues', { found: String(issues.source.length) })}</summary>
          <ul>{issues.source.map((issue, index) => <li key={index}><IssueText issue={issue} /></li>)}</ul>
        </details>
      ) : null}
    </div>
  );
}

function UploadStep({ contextId, report, onUploaded }: {
  contextId: string; report: ExportReport | null; onUploaded(report: ExportReport): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const [file, setFile] = useState<File | null>(null);
  const [scenario, setScenario] = useState('SCN01');
  const [competencies, setCompetencies] = useState('elena_usecase_competencies');
  const [missing, setMissing] = useState({ file: false, scenario: false, competencies: false });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = { file: file === null, scenario: !scenario.trim(), competencies: !competencies.trim() };
    setMissing(found);
    if (file === null || found.scenario || found.competencies) return;
    void run(async () => {
      const uploaded = await api.uploadExport(contextId, csrfToken, file, scenario.trim(), competencies.trim());
      onUploaded(uploaded);
      return { tone: 'info', text: t('build.upload.stored') };
    });
  };

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.upload.heading')}</h2>
      <p>{t('build.upload.intro')}</p>
      <form className="alm-form" noValidate onSubmit={submit}>
        <Field id={`${id}-file`} label={t('build.upload.file')} hint={t('build.upload.fileHint')}
          error={missing.file ? t('build.upload.fileRequired') : null}>
          <input id={`${id}-file`} className="alm-input" type="file" accept=".json,application/json"
            aria-invalid={missing.file} aria-describedby={describedBy(`${id}-file`, true, missing.file)}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </Field>
        <Field id={`${id}-scenario`} label={t('build.upload.scenarioLabel')} hint={t('build.upload.scenarioHint')}
          error={missing.scenario ? t('build.upload.scenarioRequired') : null}>
          <TextInput id={`${id}-scenario`} value={scenario} onChange={setScenario} invalid={missing.scenario} hint />
        </Field>
        <Field id={`${id}-competencies`} label={t('build.upload.competenciesLabel')} hint={t('build.upload.competenciesHint')}
          error={missing.competencies ? t('build.upload.competenciesRequired') : null}>
          <TextInput id={`${id}-competencies`} value={competencies} onChange={setCompetencies} invalid={missing.competencies} hint />
        </Field>
        <Button type="submit" busy={busy}>{t('build.upload.submit')}</Button>
      </form>
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
      {report ? <Report report={report} /> : null}
    </section>
  );
}

function JobStatusText({ contextId, job }: { contextId: string; job: JobView }) {
  const { t } = useTranslation();
  const proposal = job.proposal_refs[0];
  switch (job.status) {
    case 'QUEUED': return <StatusMessage>{t('build.curator.queued')}</StatusMessage>;
    case 'RUNNING': return <StatusMessage>{t('build.curator.running')}</StatusMessage>;
    case 'PROPOSED': return (
      <>
        <StatusMessage>{t('build.curator.proposed')}</StatusMessage>
        {proposal ? <p><Link to={proposalPath(contextId, proposal.id)}>{t('build.curator.review')}</Link></p> : null}
      </>
    );
    case 'ABANDONED': return <StatusMessage tone="error">{t('build.curator.abandoned')}</StatusMessage>;
    default: return (
      <>
        <StatusMessage tone="error">{t('build.curator.ended', { detail: job.detail ?? '' })}</StatusMessage>
        <p>{t('build.curator.retry')}</p>
      </>
    );
  }
}

/** The Curator works from accepted sources of this teacher, or from a search query. */
type Grounding = 'sources' | 'query';

/** The prepared sources this teacher accepted, newest first: what a Curator job may use. */
export function acceptedPreparations(jobs: JobView[], subjectKey: string | null): JobView[] {
  return jobs.filter((job) => job.job.kind === PREPARATION && job.status === 'ACCEPTED' && job.subject_key === subjectKey);
}

function CuratorStep({ contextId, report, accepted, onJob }: {
  contextId: string; report: ExportReport | null; accepted: JobView[]; onJob(job: JobView): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const [grounding, setGrounding] = useState<Grounding | null>(null);
  const [prepared, setPrepared] = useState('');
  const [scope, setScope] = useState('');
  const [query, setQuery] = useState('');
  const [missing, setMissing] = useState({ scope: false, query: false });
  const [job, setJob] = useState<JobView | null>(null);
  // One request id per command: a retry after a lost answer returns the same job.
  const requestId = useRef<string | null>(null);
  const follow = useCallback((next: JobView) => { setJob(next); onJob(next); }, [onJob]);
  useFollowedJob(contextId, job, follow);

  const mode: Grounding = grounding ?? (accepted.length > 0 ? 'sources' : 'query');
  const chosen = accepted.find((item) => item.request_id === prepared) ?? accepted[0] ?? null;

  const change = <T,>(set: (value: T) => void) => (value: T) => {
    requestId.current = null;
    set(value);
  };

  const queue = (command: Parameters<typeof api.queueCurator>[3]) => {
    requestId.current ??= newRequestId();
    const current = requestId.current;
    void run(async () => {
      const queued = await api.queueCurator(contextId, csrfToken, current, command);
      requestId.current = null;
      follow(queued);
      return null;
    });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mode === 'sources') {
      // The preparation names the export, scenario and scope its sources were prepared for.
      if (chosen === null || chosen.job.kind !== PREPARATION) return;
      const { project, plan, scenario, competencies } = chosen.job;
      queue({ export: project, scenario: scenario ?? 'SCN01', competencies: competencies ?? 'elena_usecase_competencies',
        sourceScope: plan.source_scope, preparedSources: chosen.request_id });
      return;
    }
    const found = { scope: !scope.trim(), query: !query.trim() };
    setMissing(found);
    if (report === null || found.scope || found.query) return;
    queue({ export: report.export, scenario: report.scenario, competencies: report.competencies,
      sourceScope: scope.trim(), query: query.trim() });
  };

  const running = job !== null && !ENDED_STATUSES.includes(job.status);
  let form = null;
  if (report !== null || accepted.length > 0) {
    form = (
      <form className="alm-form" noValidate onSubmit={submit}>
        {accepted.length > 0 ? (
          <fieldset className="alm-fieldset">
            <legend>{t('build.curator.grounding')}</legend>
            <label className="alm-choice">
              <input type="radio" name={`${id}-grounding`} checked={mode === 'sources'}
                onChange={() => change(setGrounding)('sources')} />
              {t('build.curator.fromSources')}
            </label>
            <label className="alm-choice">
              <input type="radio" name={`${id}-grounding`} checked={mode === 'query'}
                onChange={() => change(setGrounding)('query')} />
              {t('build.curator.fromQuery')}
            </label>
          </fieldset>
        ) : null}
        {mode === 'sources' ? (
          <Field id={`${id}-prepared`} label={t('build.curator.prepared')} hint={t('build.curator.preparedHint')}>
            <select id={`${id}-prepared`} className="alm-input" value={chosen?.request_id ?? ''}
              aria-describedby={describedBy(`${id}-prepared`, true, false)}
              onChange={(event) => change(setPrepared)(event.target.value)}>
              {accepted.map((item) => (
                <option key={item.request_id} value={item.request_id}>
                  {t('build.curator.preparedOption', {
                    count: item.job.kind === PREPARATION ? item.job.plan.documents.length : 0,
                    created: new Date(item.created).toLocaleString(),
                  })}
                </option>
              ))}
            </select>
          </Field>
        ) : report === null ? <p className="alm-muted">{t('build.curator.needsUpload')}</p> : (
          <>
            <Field id={`${id}-scope`} label={t('build.curator.scope')} hint={t('build.curator.scopeHint')}
              error={missing.scope ? t('build.curator.scopeRequired') : null}>
              <TextInput id={`${id}-scope`} value={scope} onChange={change(setScope)} invalid={missing.scope} hint />
            </Field>
            <Field id={`${id}-query`} label={t('build.curator.query')} hint={t('build.curator.queryHint')}
              error={missing.query ? t('build.curator.queryRequired') : null}>
              <TextInput id={`${id}-query`} value={query} onChange={change(setQuery)} invalid={missing.query} hint />
            </Field>
          </>
        )}
        {mode === 'sources' || report !== null ? (
          <Button type="submit" busy={busy || running}>{t('build.curator.submit')}</Button>
        ) : null}
      </form>
    );
  }

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.curator.heading')}</h2>
      <p>{t('build.curator.intro')}</p>
      {form ?? <p className="alm-muted">{t('build.curator.needsUpload')}</p>}
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
      {job ? <JobStatusText contextId={contextId} job={job} /> : null}
    </section>
  );
}

function ProjectStep({ contextId, inbox }: { contextId: string; inbox: Inbox }) {
  const { t } = useTranslation();
  const id = useId();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const [projectId, setProjectId] = useState('');
  const [missing, setMissing] = useState(false);
  const [proposal, setProposal] = useState<EntityRef | null>(null);
  const requestId = useRef<string | null>(null);
  const design = currentDesign(inbox.context);
  const projects = selectedProjects(inbox.context, inbox.entities);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = projectId.trim();
    setMissing(!value);
    if (!value || design === null) return;
    requestId.current ??= newRequestId();
    const current = requestId.current;
    void run(async () => {
      const syllabus = await api.approvedSyllabus(contextId, design);
      const proposed = await api.initializeProject(contextId, csrfToken, {
        requestId: current, projectId: value, syllabus, baseContext: refOf(inbox.context),
      });
      setProposal(proposed.proposal);
      return { tone: 'info', text: t('build.project.proposed') };
    });
  };

  let body;
  if (projects.length > 0) {
    body = (
      <>
        <ul>{projects.map((project) => <li key={project}>{t('build.project.selected', { project })}</li>)}</ul>
        <p>{t('build.project.next')}</p>
      </>
    );
  } else if (design === null) {
    body = <p className="alm-muted">{t('build.project.needsSyllabus')}</p>;
  } else {
    body = (
      <form className="alm-form" noValidate onSubmit={submit}>
        <Field id={`${id}-project`} label={t('build.project.label')} hint={t('build.project.hint')}
          error={missing ? t('build.project.required') : null}>
          <TextInput id={`${id}-project`} value={projectId} invalid={missing} hint
            onChange={(value) => { requestId.current = null; setProjectId(value); }} />
        </Field>
        <Button type="submit" busy={busy}>{t('build.project.submit')}</Button>
      </form>
    );
  }

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.project.heading')}</h2>
      <p>{t('build.project.intro')}</p>
      {body}
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
      {proposal ? <p><Link to={proposalPath(contextId, proposal.id)}>{t('build.project.review')}</Link></p> : null}
    </section>
  );
}

/** What the course has now, and what the steps below do to it. */
function CurrentSyllabus({ inbox }: { inbox: Inbox }) {
  const { t } = useTranslation();
  const name = designName(inbox.context, inbox.entities);
  return (
    <>
      <dl className="alm-facts">
        <dt>{t('build.current')}</dt>
        <dd>{name ?? t('build.noSyllabus')}</dd>
      </dl>
      {name !== null ? <p>{t('build.replaces')}</p> : null}
      <p className="alm-muted">{t('build.notKept')}</p>
    </>
  );
}

/** The jobs of the course: read when the page opens or on request; the steps add and update theirs. */
function useJobs(contextId: string) {
  const { api } = useBuildServices();
  const [jobs, setJobs] = useState<JobView[] | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    api.listJobs(contextId).then(setJobs, () => setFailed(true));
  }, [api, contextId]);
  useEffect(load, [load]);
  const update = useCallback((job: JobView) => {
    setJobs((current) => [job, ...(current ?? []).filter((item) => item.request_id !== job.request_id)]);
  }, []);
  return { jobs, failed, load, update };
}

/** Start a course from an AIM-PRO model: upload it, prepare its sources, let the Curator draft the syllabus, then initialize the project. */
export function BuildPage({ contextId }: { contextId: string }) {
  const { t } = useTranslation();
  const { state, reload } = useInbox(contextId);
  const subjectKey = useSubjectKey();
  const [report, setReport] = useState<ExportReport | null>(null);
  const { jobs, failed, load, update } = useJobs(contextId);
  const [opened, setOpened] = useState<JobView | null>(null);
  return (
    <>
      <p><Link to={coursePath(contextId)}>{t('build.back')}</Link></p>
      <h1>{t('build.title')}</h1>
      <p>{t('build.intro')}</p>
      {state.status === 'loading' ? <StatusMessage>{t('course.loading')}</StatusMessage> : null}
      {state.status === 'error' ? <LoadFailure reason={state.reason} onRetry={reload} /> : null}
      {state.status === 'ready' ? (
        <>
          <p><Link to={inboxPath(contextId)}>{t('course.review', { count: state.inbox.pending.length })}</Link></p>
          <CurrentSyllabus inbox={state.inbox} />
          <JobsList contextId={contextId} jobs={jobs} failed={failed} subjectKey={subjectKey} onReload={load}
            onOpen={setOpened} />
          <UploadStep contextId={contextId} report={report} onUploaded={setReport} />
          <SourcesStep contextId={contextId} report={report} opened={opened} onJob={update} />
          <CuratorStep contextId={contextId} report={report} accepted={acceptedPreparations(jobs ?? [], subjectKey)}
            onJob={update} />
          <ProjectStep contextId={contextId} inbox={state.inbox} />
        </>
      ) : null}
    </>
  );
}
