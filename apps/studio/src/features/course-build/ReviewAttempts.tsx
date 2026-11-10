import { StatusMessage } from '@alm/ui';
import { useState } from 'react';
import type { SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';

import type { SyllabusAttempt } from './buildApi';
import { useBuildServices } from './BuildServices';

export type AttemptOutcome = 'accepted' | 'rejected' | 'uncertain' | 'checks';

/** How one draft ended: accepted only with an ACCEPT verdict and both checks of the review agent passed. */
export function attemptOutcome(attempt: SyllabusAttempt): AttemptOutcome {
  const review = attempt.review;
  if (!review) return 'checks';
  if (review.verdict === 'ACCEPT' && review.source_alignment && review.citation_support) return 'accepted';
  return review.verdict === 'UNCERTAIN' ? 'uncertain' : 'rejected';
}

/**
 * The Curator's drafts of an ended syllabus job and how each was judged, read when the teacher opens them.
 * The review agent's reason is shown as its own words, labelled as model text.
 */
export function ReviewAttempts({ contextId, requestId }: { contextId: string; requestId: string }) {
  const { t } = useTranslation();
  const { api } = useBuildServices();
  const [attempts, setAttempts] = useState<SyllabusAttempt[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [asked, setAsked] = useState(false);

  const open = (event: SyntheticEvent<HTMLDetailsElement>) => {
    if (!event.currentTarget.open || asked) return;
    setAsked(true);
    api.readSyllabusReviews(contextId, requestId).then((read) => setAttempts(read.attempts), () => setFailed(true));
  };

  let body;
  if (failed) body = <StatusMessage tone="error">{t('build.reviews.failed')}</StatusMessage>;
  else if (attempts === null) body = <StatusMessage>{t('build.reviews.loading')}</StatusMessage>;
  else if (attempts.length === 0) body = <p className="alm-muted">{t('build.reviews.none')}</p>;
  else {
    const answer = (value: boolean) => t(value ? 'build.reviews.yes' : 'build.reviews.no');
    body = (
      <ol data-testid="review-attempts">
        {attempts.map((attempt) => (
          <li key={attempt.attempt}>
            <p>{t('build.reviews.attempt', { attempt: attempt.attempt,
              outcome: t(`build.reviews.outcome.${attemptOutcome(attempt)}`) })}</p>
            {attempt.review ? (
              <>
                <p>{t('build.reviews.flags', { alignment: answer(attempt.review.source_alignment),
                  citations: answer(attempt.review.citation_support) })}</p>
                <p>{t('build.reviews.reason', { reason: attempt.review.reason })}</p>
              </>
            ) : <p>{t('build.reviews.check', { check: attempt.check })}</p>}
          </li>
        ))}
      </ol>
    );
  }
  return (
    <details onToggle={open}>
      <summary>{t('build.reviews.summary')}</summary>
      <p className="alm-muted">{t('build.reviews.intro')}</p>
      {body}
    </details>
  );
}
