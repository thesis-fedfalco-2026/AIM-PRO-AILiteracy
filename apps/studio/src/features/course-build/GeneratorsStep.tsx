import { Button, StatusMessage } from '@alm/ui';
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { readable, refOf } from '../review/model';
import { proposalPath } from '../review/paths';
import { ReviewError } from '../review/reviewApi';
import type { EntityRef } from '../review/reviewApi';
import { useCsrfToken, useReviewServices } from '../review/ReviewServices';
import { ENDED_STATUSES } from './buildApi';
import type { GeneratorCommand, GeneratorKind, JobView, ProjectInspection } from './buildApi';
import { useBuildServices } from './BuildServices';
import type { Notice } from './parts';
import { describedBy, Field, useFollowedJob, useStep } from './parts';

const EVALUATOR: GeneratorKind = 'generate-project-assessments';

/** The forms in the order of the cycle: the Teacher and Trainer build on the applied assessments. */
const GENERATORS: { kind: GeneratorKind; role: 'evaluator' | 'teacher' | 'trainer'; step: number }[] = [
  { kind: EVALUATOR, role: 'evaluator', step: 5 },
  { kind: 'generate-project-teacher', role: 'teacher', step: 6 },
  { kind: 'generate-project-trainer', role: 'trainer', step: 7 },
];

/** What the forms send: the course's current version and the project's current selections. */
interface Course {
  base: EntityRef;
  inspection: ProjectInspection;
}

type CourseState = { status: 'loading' } | { status: 'ready'; course: Course; reloading: boolean } | { status: 'error' };

/**
 * The course version and the project inspection, read on mount and on `reload`. While they are read again
 * the forms keep what they show, with sending disabled, so a refusal stays on screen.
 */
function useCourse(contextId: string, projectId: string) {
  const { api: review } = useReviewServices();
  const { api } = useBuildServices();
  const [state, setState] = useState<CourseState>({ status: 'loading' });
  const [generation, setGeneration] = useState(0);
  useEffect(() => {
    let current = true;
    Promise.all([review.inbox(contextId), api.inspectProject(contextId, projectId)]).then(
      ([inbox, inspection]) => current && setState({
        status: 'ready', course: { base: refOf(inbox.context), inspection }, reloading: false }),
      () => current && setState({ status: 'error' }),
    );
    return () => {
      current = false;
    };
  }, [api, review, contextId, projectId, generation]);
  const reload = useCallback(() => {
    setState((now) => (now.status === 'ready' ? { ...now, reloading: true } : { status: 'loading' }));
    setGeneration((value) => value + 1);
  }, []);
  return { state, reload };
}

/** The applied assessments of the project: what the Teacher and Trainer build on. */
export const assessmentsOf = (inspection: ProjectInspection): EntityRef[] =>
  inspection.manifest.artifacts.filter((artifact) => artifact.kind === 'ASSESSMENT').map((artifact) => artifact.resource);

const lines = (text: string) => text.split('\n').map((line) => line.trim()).filter(Boolean);

/** The exact refs a form sends. */
function Refs({ project, base, assessments }: { project: EntityRef; base: EntityRef; assessments?: EntityRef[] | undefined }) {
  const { t } = useTranslation();
  const refText = (ref: EntityRef) => <><code>{ref.id}</code> {t('build.generators.version', { version: ref.version })}</>;
  return (
    <dl className="alm-facts" data-testid="sent-refs">
      <dt>{t('build.generators.project')}</dt>
      <dd>{refText(project)}</dd>
      <dt>{t('build.generators.base')}</dt>
      <dd>{refText(base)}</dd>
      {assessments ? (
        <>
          <dt>{t('build.generators.assessments')}</dt>
          <dd>
            {assessments.length === 0 ? t('build.generators.noAssessments')
              : <ul>{assessments.map((ref) => <li key={`${ref.id}\u0000${ref.version}`}>{refText(ref)}</li>)}</ul>}
          </dd>
        </>
      ) : null}
    </dl>
  );
}

function GeneratorJob({ contextId, job }: { contextId: string; job: JobView }) {
  const { t } = useTranslation();
  const proposal = job.proposal_refs[0];
  switch (job.status) {
    case 'QUEUED': return <StatusMessage>{t('build.generators.queued')}</StatusMessage>;
    case 'RUNNING': return <StatusMessage>{t('build.generators.running')}</StatusMessage>;
    case 'PROPOSED': return (
      <>
        <StatusMessage>{t('build.generators.proposed')}</StatusMessage>
        {proposal ? <p><Link to={proposalPath(contextId, proposal.id)}>{t('build.generators.review')}</Link></p> : null}
      </>
    );
    case 'ABANDONED': return <StatusMessage tone="error">{t('build.generators.abandoned')}</StatusMessage>;
    default: return <StatusMessage tone="error">{t('build.generators.ended', { detail: job.detail ?? '' })}</StatusMessage>;
  }
}

/** A write whose 409 means the course changed: the form is read again and says so. */
function useStaleAware(onReload: () => void) {
  const { t } = useTranslation();
  return async (write: () => Promise<Notice | null>): Promise<Notice | null> => {
    try {
      return await write();
    } catch (error) {
      if (!(error instanceof ReviewError && error.reason === 'conflict')) throw error;
      onReload();
      return { tone: 'error', text: t('build.generators.stale') };
    }
  };
}

function GeneratorForm({ contextId, kind, role, step, course, reloading, onReload, onJob }: {
  contextId: string; kind: GeneratorKind; role: 'evaluator' | 'teacher' | 'trainer'; step: number;
  course: Course; reloading: boolean; onReload(): void; onJob(job: JobView): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const staleAware = useStaleAware(onReload);
  const [requirements, setRequirements] = useState('');
  const [job, setJob] = useState<JobView | null>(null);
  // One request id per command: a retry after a lost answer returns the same job; a changed command is new.
  const sent = useRef<{ key: string; requestId: string } | null>(null);
  const follow = useCallback((next: JobView) => { setJob(next); onJob(next); }, [onJob]);
  useFollowedJob(contextId, job, follow);

  const assessments = assessmentsOf(course.inspection);
  const command: GeneratorCommand = {
    project: course.inspection.project, baseContext: course.base,
    assessments: kind === EVALUATOR ? [] : assessments, requirements: lines(requirements),
  };
  const blocked = kind !== EVALUATOR && assessments.length === 0;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (blocked || reloading) return;
    const key = JSON.stringify(command);
    if (sent.current?.key !== key) sent.current = { key, requestId: newRequestId() };
    const { requestId } = sent.current;
    void run(() => staleAware(async () => {
      follow(await api.queueGenerator(contextId, csrfToken, requestId, kind, command));
      return null;
    }));
  };

  const running = job !== null && !ENDED_STATUSES.includes(job.status);
  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t(`build.generators.${role}.heading`, { step: String(step) })}</h2>
      <p>{t(`build.generators.${role}.intro`)}</p>
      <h3>{t('build.generators.sends')}</h3>
      <Refs project={command.project} base={command.baseContext} assessments={kind === EVALUATOR ? undefined : assessments} />
      {blocked ? <p className="alm-muted">{t('build.generators.needsAssessments')}</p> : (
        <form className="alm-form" noValidate onSubmit={submit}>
          <Field id={`${id}-requirements`} label={t('build.generators.requirements')} hint={t('build.generators.requirementsHint')}>
            <textarea id={`${id}-requirements`} className="alm-input" rows={3} value={requirements}
              aria-describedby={describedBy(`${id}-requirements`, true, false)}
              onChange={(event) => setRequirements(event.target.value)} />
          </Field>
          <Button type="submit" busy={busy || running || reloading}>{t(`build.generators.${role}.submit`)}</Button>
        </form>
      )}
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
      {job ? <GeneratorJob contextId={contextId} job={job} /> : null}
    </section>
  );
}

function CompletionForm({ contextId, course, reloading, onReload }: {
  contextId: string; course: Course; reloading: boolean; onReload(): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const staleAware = useStaleAware(onReload);
  const [proposal, setProposal] = useState<EntityRef | null>(null);
  const sent = useRef<{ key: string; requestId: string } | null>(null);
  const { project } = course.inspection;
  const trainer = course.inspection.manifest.artifacts.some((artifact) => artifact.kind === 'TRAINER_CONTENT');
  const stale = course.inspection.stale_dependencies.length > 0;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (reloading) return;
    const key = JSON.stringify([project, course.base]);
    if (sent.current?.key !== key) sent.current = { key, requestId: newRequestId() };
    const { requestId } = sent.current;
    void run(() => staleAware(async () => {
      const proposed = await api.proposeCompletionRules(contextId, csrfToken, { requestId, project, baseContext: course.base });
      setProposal(proposed.proposal);
      return { tone: 'info', text: t('build.completion.proposed') };
    }));
  };

  let body;
  if (!trainer) body = <p className="alm-muted">{t('build.completion.needsTrainer')}</p>;
  else if (stale) body = <p className="alm-muted">{t('build.completion.needsFresh')}</p>;
  else {
    body = (
      <form className="alm-form" noValidate onSubmit={submit}>
        <Button type="submit" busy={busy || reloading}>{t('build.completion.submit')}</Button>
      </form>
    );
  }
  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.completion.heading')}</h2>
      <p>{t('build.completion.intro')}</p>
      <h3>{t('build.generators.sends')}</h3>
      <Refs project={project} base={course.base} />
      {body}
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
      {proposal ? <p><Link to={proposalPath(contextId, proposal.id)}>{t('build.completion.review')}</Link></p> : null}
    </section>
  );
}

/** Content made from an earlier version of what it depends on, which the author generates again. */
function StaleContent({ inspection }: { inspection: ProjectInspection }) {
  const { t } = useTranslation();
  if (inspection.stale_dependencies.length === 0) return null;
  const targets = [...new Set(inspection.stale_dependencies.map((finding) => readable(finding.target)))];
  return <StatusMessage tone="error">{t('build.generators.staleContent', { targets: targets.join(', ') })}</StatusMessage>;
}

/** The Evaluator, Teacher and Trainer forms and the completion rules of the course's project. */
export function GeneratorsStep({ contextId, projectId, onJob }: {
  contextId: string; projectId: string; onJob(job: JobView): void;
}) {
  const { t } = useTranslation();
  const { state, reload } = useCourse(contextId, projectId);
  if (state.status === 'loading') return <StatusMessage>{t('build.generators.loading')}</StatusMessage>;
  if (state.status === 'error') {
    return (
      <>
        <StatusMessage tone="error">{t('build.generators.failed')}</StatusMessage>
        <Button variant="secondary" onClick={reload}>{t('build.generators.reload')}</Button>
      </>
    );
  }
  const { course, reloading } = state;
  return (
    <>
      <StaleContent inspection={course.inspection} />
      {GENERATORS.map(({ kind, role, step }) => (
        <GeneratorForm key={kind} contextId={contextId} kind={kind} role={role} step={step} course={course}
          reloading={reloading} onReload={reload} onJob={onJob} />
      ))}
      <CompletionForm contextId={contextId} course={course} reloading={reloading} onReload={reload} />
    </>
  );
}
