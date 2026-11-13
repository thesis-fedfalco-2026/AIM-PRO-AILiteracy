import { Button, StatusMessage } from '@alm/ui';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { proposalPath } from '../review/paths';
import { CURATOR, DISCOVERY, GENERATORS, PREPARATION, REVISION } from './buildApi';
import type { JobView } from './buildApi';
import { ReviewAttempts } from './ReviewAttempts';
import type { AttemptSource } from './ReviewAttempts';

type KindKey = `build.jobs.kind.${'discovery' | 'preparation' | 'curator' | 'revision' | 'assessments' | 'teacher' | 'trainer' | 'other'}`;

const KINDS: Record<string, KindKey> = {
  [DISCOVERY]: 'build.jobs.kind.discovery',
  [PREPARATION]: 'build.jobs.kind.preparation',
  [CURATOR]: 'build.jobs.kind.curator',
  [REVISION]: 'build.jobs.kind.revision',
  'generate-project-assessments': 'build.jobs.kind.assessments',
  'generate-project-teacher': 'build.jobs.kind.teacher',
  'generate-project-trainer': 'build.jobs.kind.trainer',
};

/**
 * Whose drafts the review agent judged in this job, if the signed-in teacher may read them: an ended Curator,
 * Evaluator, Teacher or Trainer job of that teacher.
 */
export function reviewAttemptsOf(job: JobView, own: boolean): AttemptSource | null {
  if (!own || (job.status !== 'PROPOSED' && job.status !== 'FAILED')) return null;
  if (job.job.kind === CURATOR || job.job.kind === REVISION) return 'syllabus';
  return GENERATORS.includes(job.job.kind) ? 'generation' : null;
}

/** What a teacher can do next with a job of the list, if anything. */
function NextAction({ contextId, job, own, onOpen }: {
  contextId: string; job: JobView; own: boolean; onOpen(job: JobView): void;
}) {
  const { t } = useTranslation();
  const proposal = job.proposal_refs[0];
  if (proposal) return <Link to={proposalPath(contextId, proposal.id)}>{t('build.jobs.review')}</Link>;
  if (!own) return null;
  if (job.job.kind === DISCOVERY && job.status === 'COMPLETED') {
    return <Button variant="secondary" onClick={() => onOpen(job)}>{t('build.jobs.pick')}</Button>;
  }
  if (job.job.kind === PREPARATION && job.status === 'AWAITING_CHOICE') {
    return <Button variant="secondary" onClick={() => onOpen(job)}>{t('build.jobs.choose')}</Button>;
  }
  return null;
}

function JobAttempts({ contextId, job, own }: { contextId: string; job: JobView; own: boolean }) {
  const source = reviewAttemptsOf(job, own);
  return source ? <ReviewAttempts contextId={contextId} requestId={job.request_id} source={source} /> : null;
}

/** The jobs of the course, newest first: what runs, what ended and what waits for the teacher. */
export function JobsList({ contextId, jobs, failed, subjectKey, onReload, onOpen }: {
  contextId: string; jobs: JobView[] | null; failed: boolean; subjectKey: string | null;
  onReload(): void; onOpen(job: JobView): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  let body;
  if (failed) body = <StatusMessage tone="error">{t('build.jobs.failed')}</StatusMessage>;
  else if (jobs === null) body = <StatusMessage>{t('build.jobs.loading')}</StatusMessage>;
  else if (jobs.length === 0) body = <p className="alm-muted">{t('build.jobs.none')}</p>;
  else {
    body = (
      <ul data-testid="course-jobs">
        {jobs.map((job) => (
          <li key={job.request_id}>
            <p>
              {t('build.jobs.item', {
                kind: t(KINDS[job.job.kind] ?? 'build.jobs.kind.other'),
                status: t(`build.jobs.status.${job.status}`),
                created: new Date(job.created).toLocaleString(),
              })}
            </p>
            {job.blocks ? <p>{t('build.jobs.blocks', { written: job.blocks.written, count: job.blocks.count })}</p> : null}
            {job.detail ? <p className="alm-muted">{t('build.jobs.detail', { detail: job.detail })}</p> : null}
            <NextAction contextId={contextId} job={job} own={job.subject_key === subjectKey} onOpen={onOpen} />
            <JobAttempts contextId={contextId} job={job} own={job.subject_key === subjectKey} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('build.jobs.heading')}</h2>
      <p>{t('build.jobs.intro')}</p>
      {body}
      <Button variant="secondary" onClick={onReload}>{t('build.jobs.reload')}</Button>
    </section>
  );
}
