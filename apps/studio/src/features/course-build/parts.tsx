import { useSession } from '@alm/auth';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { ReviewError } from '../review/reviewApi';
import type { ReviewFailure } from '../review/reviewApi';
import { ENDED_STATUSES } from './buildApi';
import type { JobView } from './buildApi';
import { useBuildServices } from './BuildServices';

export type Notice = { tone: 'info' | 'error'; text: string };

/** A step's write: busy while it runs, its failure as a notice; an ended session goes back to sign-in. */
export function useStep() {
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

export function Field({ id, label, hint, error, children }: {
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

export const describedBy = (id: string, hint: boolean, error: boolean) =>
  [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined;

export function TextInput({ id, value, onChange, invalid, hint }: {
  id: string; value: string; onChange(value: string): void; invalid: boolean; hint: boolean;
}) {
  return (
    <input id={id} className="alm-input" type="text" autoComplete="off" spellCheck={false} value={value}
      aria-invalid={invalid} aria-describedby={describedBy(id, hint, invalid)}
      onChange={(event) => onChange(event.target.value)} />
  );
}

/** Follow a job until the worker is done with it: read it again every `pollMs` and report each read. */
export function useFollowedJob(contextId: string, job: JobView | null, onJob: (job: JobView) => void) {
  const { api, pollMs } = useBuildServices();
  useEffect(() => {
    if (job === null || ENDED_STATUSES.includes(job.status)) return;
    const timer = setTimeout(() => {
      api.readJob(contextId, job.request_id).then(onJob, () => onJob({ ...job }));
    }, pollMs);
    return () => clearTimeout(timer);
  }, [api, contextId, job, onJob, pollMs]);
}

/** The signed-in subject, or null. */
export function useSubjectKey(): string | null {
  const { state } = useSession();
  return state.status === 'signed-in' ? state.session.subjectKey : null;
}
