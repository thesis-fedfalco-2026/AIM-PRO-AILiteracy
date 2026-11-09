import { Button, StatusMessage } from '@alm/ui';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import type { JsonValue, ReviewFailure } from './reviewApi';

const flat = (value: JsonValue) => Array.isArray(value) && value.every((item) => item === null || typeof item !== 'object');

/** A JSON value as people read it: text as it is, a list of plain values on one line, anything else as indented JSON. */
export function JsonText({ value }: { value: JsonValue | undefined }) {
  const { t } = useTranslation();
  if (value === undefined) return <span className="alm-muted">{t('review.changes.absent')}</span>;
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, flat(value) ? undefined : 2);
  return <pre className="alm-code">{text}</pre>;
}

/** A table that may be wider than the page scrolls on its own and can be scrolled with the keyboard. */
export function ScrollRegion({ labelledBy, label, children }: {
  labelledBy?: string; label?: string; children: ReactNode;
}) {
  const name = labelledBy ? { 'aria-labelledby': labelledBy } : { 'aria-label': label };
  return (
    <div className="alm-scroll" role="region" tabIndex={0} {...name}>
      {children}
    </div>
  );
}

export function LoadFailure({ reason, onRetry }: { reason: ReviewFailure; onRetry: () => void }) {
  const { t } = useTranslation();
  const message = reason === 'unavailable' ? t('review.errors.unavailable')
    : reason === 'forbidden' ? t('review.errors.forbidden') : t('review.errors.failed');
  return (
    <>
      <StatusMessage tone="error">{message}</StatusMessage>
      <Button variant="secondary" onClick={onRetry}>{t('review.errors.retry')}</Button>
    </>
  );
}

const STATUS_KEYS = {
  AWAITING_DECISION: 'review.status.awaitingDecision',
  APPROVED: 'review.status.approved',
  REJECTED: 'review.status.rejected',
  DRAFT: 'review.status.draft',
  APPLIED: 'review.status.applied',
  STALE: 'review.status.stale',
} as const;

/** The label of a proposal status; a status this studio does not know is shown as recorded. */
export function useStatusLabel() {
  const { t } = useTranslation();
  return (status: string) => (Object.hasOwn(STATUS_KEYS, status)
    ? t(STATUS_KEYS[status as keyof typeof STATUS_KEYS]) : status);
}
