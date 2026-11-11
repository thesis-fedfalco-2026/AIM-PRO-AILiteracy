import { StatusMessage } from '@alm/ui';
import { useState } from 'react';
import type { SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';

import type { GenerationAttempt, SyllabusAttempt } from './buildApi';
import { useBuildServices } from './BuildServices';

export type AttemptOutcome = 'accepted' | 'rejected' | 'uncertain' | 'checks';

/** Whose drafts: the Curator's syllabus (Chat 20), or the Evaluator's, Teacher's or Trainer's content (S09c). */
export type AttemptSource = 'syllabus' | 'generation';

type Attempt = SyllabusAttempt | GenerationAttempt;

/** How one draft ended: accepted only with an ACCEPT verdict and every check of the review agent passed. */
export function attemptOutcome(attempt: Attempt): AttemptOutcome {
  const review = attempt.review;
  if (!review) return 'checks';
  const passed = Object.values(review).every((value) => value !== false);
  if (review.verdict === 'ACCEPT' && passed) return 'accepted';
  return review.verdict === 'UNCERTAIN' ? 'uncertain' : 'rejected';
}

/** The review agent's checks of one draft, as a sentence. */
function Flags({ review }: { review: NonNullable<Attempt['review']> }) {
  const { t } = useTranslation();
  const answer = (value: boolean) => t(value ? 'build.reviews.yes' : 'build.reviews.no');
  if ('intent_correct' in review) {
    return <p>{t('build.reviews.generationFlags', { alignment: answer(review.source_alignment),
      citations: answer(review.citation_support), intent: answer(review.intent_correct),
      complete: answer(review.content_complete) })}</p>;
  }
  return <p>{t('build.reviews.flags', { alignment: answer(review.source_alignment),
    citations: answer(review.citation_support) })}</p>;
}

/**
 * The drafts of an ended job and how each was judged, read when the teacher opens them.
 * The review agent's reason is shown as its own words, labelled as model text.
 */
export function ReviewAttempts({ contextId, requestId, source = 'syllabus' }: {
  contextId: string; requestId: string; source?: AttemptSource;
}) {
  const { t } = useTranslation();
  const { api } = useBuildServices();
  const [attempts, setAttempts] = useState<Attempt[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [asked, setAsked] = useState(false);

  const open = (event: SyntheticEvent<HTMLDetailsElement>) => {
    if (!event.currentTarget.open || asked) return;
    setAsked(true);
    const read = source === 'syllabus' ? api.readSyllabusReviews(contextId, requestId)
      : api.readGenerationReviews(contextId, requestId);
    read.then((reviews) => setAttempts(reviews.attempts), () => setFailed(true));
  };

  let body;
  if (failed) body = <StatusMessage tone="error">{t('build.reviews.failed')}</StatusMessage>;
  else if (attempts === null) body = <StatusMessage>{t('build.reviews.loading')}</StatusMessage>;
  else if (attempts.length === 0) body = <p className="alm-muted">{t('build.reviews.none')}</p>;
  else {
    body = (
      <ol data-testid="review-attempts">
        {attempts.map((attempt) => (
          <li key={attempt.attempt}>
            <p>{t('build.reviews.attempt', { attempt: attempt.attempt,
              outcome: t(`build.reviews.outcome.${attemptOutcome(attempt)}`) })}</p>
            {attempt.review ? (
              <>
                <Flags review={attempt.review} />
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
      <summary>{t(source === 'syllabus' ? 'build.reviews.summary' : 'build.reviews.generation.summary')}</summary>
      <p className="alm-muted">{t(source === 'syllabus' ? 'build.reviews.intro' : 'build.reviews.generation.intro')}</p>
      {body}
    </details>
  );
}
