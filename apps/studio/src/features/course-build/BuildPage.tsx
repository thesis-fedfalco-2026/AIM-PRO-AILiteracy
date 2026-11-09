import { useSession } from '@alm/auth';
import { Button, StatusMessage } from '@alm/ui';
import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { refOf } from '../review/model';
import { LoadFailure } from '../review/parts';
import { coursePath, inboxPath, proposalPath } from '../review/paths';
import { ReviewError } from '../review/reviewApi';
import type { EntityRef, Inbox, JsonValue, ReviewFailure } from '../review/reviewApi';
import { useCsrfToken } from '../review/ReviewServices';
import { plainIssues } from '../review/teacher';
import { IssueText } from '../review/TeacherView';
import { useInbox } from '../review/useInbox';
import { FINAL_STATUSES } from './buildApi';
import type { ExportReport, JobView } from './buildApi';
import { useBuildServices } from './BuildServices';
import { currentDesign, selectedProjects } from './projects';

type Notice = { tone: 'info' | 'error'; text: string };

/** A step's write: busy while it runs, its failure as a notice; an ended session goes back to sign-in. */
function useStep() {
  const { t } = useTranslation();
  const { reload: reloadSession } = useSession();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const failure = (reason: ReviewFailure, detail: string) => {
    switch (reason) {
      case 'refused': return t('build.errors.refused', { detail });
      case 'conflict': return t('build.errors.conflict', { detail });
      case 'forbidden': return t('build.errors.forbidden');
      case 'unavailable': return t('review.errors.unavailable');
      default: return t('build.errors.failed');
    }
  };
  const run = async (action: () => Promise<Notice | null>) => {
    setBusy(true);
    setNotice(null);
    try {
      setNotice(await action());
    } catch (error) {
      const reason = error instanceof ReviewError ? error.reason : 'failed';
      if (reason === 'signed-out') void reloadSession();
      else setNotice({ tone: 'error', text: failure(reason, error instanceof ReviewError ? error.detail ?? '' : '') });
    }
    setBusy(false);
  };
  return { busy, notice, run };
}

function Field({ id, label, hint, error, children }: {
  id: string; label: string; hint?: string; error?: string | null; children: ReactNode;
}) {
  return (
    <div className="alm-field">
      <label htmlFor={id}>{label}</label>
      {hint ? <p id={`${id}-hint`} className="alm-muted">{hint}</p> : null}
      {error ? <p id={`${id}-error`} className="alm-field-error">{error}</p> : null}
      {children}
    </div>
  );
}

const describedBy = (id: string, hint: boolean, error: boolean) =>
  [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined;

function TextInput({ id, value, onChange, invalid, hint }: {
  id: string; value: string; onChange(value: string): void; invalid: boolean; hint: boolean;
}) {
  return (
    <input id={id} className="alm-input" type="text" autoComplete="off" spellCheck={false} value={value}
      aria-invalid={invalid} aria-describedby={describedBy(id, hint, invalid)}
      onChange={(event) => onChange(event.target.value)} />
  );
}

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
    default: return <StatusMessage tone="error">{t('build.curator.ended', { detail: job.detail ?? '' })}</StatusMessage>;
  }
}

function CuratorStep({ contextId, report }: { contextId: string; report: ExportReport | null }) {
  const { t } = useTranslation();
  const id = useId();
  const { api, pollMs, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const [scope, setScope] = useState('');
  const [query, setQuery] = useState('');
  const [missing, setMissing] = useState({ scope: false, query: false });
  const [job, setJob] = useState<JobView | null>(null);
  // One request id per command: a retry after a lost answer returns the same job.
  const requestId = useRef<string | null>(null);

  useEffect(() => {
    if (job === null || FINAL_STATUSES.includes(job.status)) return;
    const timer = setTimeout(() => {
      api.readJob(contextId, job.request_id).then(setJob, () => setJob({ ...job }));
    }, pollMs);
    return () => clearTimeout(timer);
  }, [api, contextId, job, pollMs]);

  const change = (set: (value: string) => void) => (value: string) => {
    requestId.current = null;
    set(value);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = { scope: !scope.trim(), query: !query.trim() };
    setMissing(found);
    if (report === null || found.scope || found.query) return;
    requestId.current ??= newRequestId();
    const current = requestId.current;
    void run(async () => {
      const queued = await api.queueCurator(contextId, csrfToken, current, {
        export: report.export, scenario: report.scenario, competencies: report.competencies,
        sourceScope: scope.trim(), query: query.trim(),
      });
      requestId.current = null;
      setJob(queued);
      return null;
    });
  };

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.curator.heading')}</h2>
      <p>{t('build.curator.intro')}</p>
      {report === null ? <p className="alm-muted">{t('build.curator.needsUpload')}</p> : (
        <form className="alm-form" noValidate onSubmit={submit}>
          <Field id={`${id}-scope`} label={t('build.curator.scope')} hint={t('build.curator.scopeHint')}
            error={missing.scope ? t('build.curator.scopeRequired') : null}>
            <TextInput id={`${id}-scope`} value={scope} onChange={change(setScope)} invalid={missing.scope} hint />
          </Field>
          <Field id={`${id}-query`} label={t('build.curator.query')} hint={t('build.curator.queryHint')}
            error={missing.query ? t('build.curator.queryRequired') : null}>
            <TextInput id={`${id}-query`} value={query} onChange={change(setQuery)} invalid={missing.query} hint />
          </Field>
          <Button type="submit" busy={busy || (job !== null && !FINAL_STATUSES.includes(job.status))}>
            {t('build.curator.submit')}
          </Button>
        </form>
      )}
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
    body = <ul>{projects.map((project) => <li key={project}>{t('build.project.selected', { project })}</li>)}</ul>;
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

/** Start a course from an AIM-PRO model: upload it, let the Curator draft the syllabus, then initialize the project. */
export function BuildPage({ contextId }: { contextId: string }) {
  const { t } = useTranslation();
  const { state, reload } = useInbox(contextId);
  const [report, setReport] = useState<ExportReport | null>(null);
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
          <UploadStep contextId={contextId} report={report} onUploaded={setReport} />
          <CuratorStep contextId={contextId} report={report} />
          <ProjectStep contextId={contextId} inbox={state.inbox} />
        </>
      ) : null}
    </>
  );
}
