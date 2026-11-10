import { Button, StatusMessage } from '@alm/ui';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { REVISION } from '../course-build/buildApi';
import type { JobView } from '../course-build/buildApi';
import { useBuildServices } from '../course-build/BuildServices';
import { useFollowedJob } from '../course-build/parts';
import { proposalPath } from './paths';
import { ReviewError } from './reviewApi';
import { useCsrfToken } from './ReviewServices';

/**
 * After a revision request on a syllabus proposal: ask the Curator for a revised
 * syllabus (a revision job), follow it and open the new proposal. A revision job
 * already started for this proposal is shown again when the page opens.
 */
export function RevisionStep({ contextId, proposalId, reason }: { contextId: string; proposalId: string; reason: string }) {
  const { t } = useTranslation();
  const { api, newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const [requestId] = useState(newRequestId);
  const [job, setJob] = useState<JobView | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const follow = useCallback((next: JobView) => setJob(next), []);
  useFollowedJob(contextId, job, follow);

  useEffect(() => {
    let current = true;
    api.listJobs(contextId).then((jobs) => {
      const started = jobs.find((item) => item.job.kind === REVISION && 'proposal' in item.job && item.job.proposal === proposalId);
      if (current && started) setJob(started);
    }, () => undefined);
    return () => {
      current = false;
    };
  }, [api, contextId, proposalId]);

  const ask = () => {
    setBusy(true);
    setFailure(null);
    api.queueRevision(contextId, csrfToken, requestId, proposalId).then(setJob, (error: unknown) => {
      setFailure(error instanceof ReviewError && error.detail ? error.detail : t('build.errors.failed'));
    }).finally(() => setBusy(false));
  };

  const revised = job?.proposal_refs[0];
  return (
    <section aria-labelledby="syllabus-revision">
      <h2 id="syllabus-revision">{t('review.syllabus.revision.heading')}</h2>
      <p>{t('review.syllabus.revision.requested', { reason })}</p>
      {job === null ? (
        <>
          <p>{t('review.syllabus.revision.intro')}</p>
          <Button onClick={ask} disabled={busy}>{t('review.syllabus.revision.ask')}</Button>
        </>
      ) : (
        <StatusMessage tone={job.status === 'REJECTED' || job.status === 'FAILED' ? 'error' : 'info'}>
          {t('review.syllabus.revision.status', { status: t(`build.jobs.status.${job.status}`) })}
          {job.detail ? ` ${t('build.jobs.detail', { detail: job.detail })}` : ''}
        </StatusMessage>
      )}
      {revised ? <p><Link to={proposalPath(contextId, revised.id)}>{t('review.syllabus.revision.open')}</Link></p> : null}
      {failure ? <StatusMessage tone="error">{failure}</StatusMessage> : null}
    </section>
  );
}
