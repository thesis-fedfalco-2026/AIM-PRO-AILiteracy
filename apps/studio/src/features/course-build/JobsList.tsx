import { Button, StatusMessage } from '@alm/ui';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { proposalPath } from '../review/paths';
import { CURATOR, DISCOVERY, PREPARATION } from './buildApi';
import type { JobView } from './buildApi';

type KindKey = `build.jobs.kind.${'discovery' | 'preparation' | 'curator' | 'assessments' | 'teacher' | 'trainer' | 'other'}`;

const KINDS: Record<string, KindKey> = {
  [DISCOVERY]: 'build.jobs.kind.discovery',
  [PREPARATION]: 'build.jobs.kind.preparation',
  [CURATOR]: 'build.jobs.kind.curator',
  'generate-project-assessments': 'build.jobs.kind.assessments',
  'generate-project-teacher': 'build.jobs.kind.teacher',
  'generate-project-trainer': 'build.jobs.kind.trainer',
};

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
            {job.detail ? <p className="alm-muted">{t('build.jobs.detail', { detail: job.detail })}</p> : null}
            <NextAction contextId={contextId} job={job} own={job.subject_key === subjectKey} onOpen={onOpen} />
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
