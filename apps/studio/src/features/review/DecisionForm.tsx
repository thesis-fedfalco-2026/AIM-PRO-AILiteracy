import { Button } from '@alm/ui';
import { useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import type { DecisionKind } from './reviewApi';

export const DECISION_KEYS = {
  APPROVE: 'review.decision.approve',
  REJECT: 'review.decision.reject',
  REQUEST_REVISION: 'review.decision.requestRevision',
} as const satisfies Record<DecisionKind, string>;

const DECISIONS = Object.keys(DECISION_KEYS) as DecisionKind[];

export interface DecisionFormProps {
  busy: boolean;
  onDecide(decision: DecisionKind, reason: string): void;
}

/** Choose a decision and give its reason; the page records it on the exact payload shown above. */
export function DecisionForm({ busy, onDecide }: DecisionFormProps) {
  const { t } = useTranslation();
  const id = useId();
  const [decision, setDecision] = useState<DecisionKind | null>(null);
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<{ decision: boolean; reason: boolean }>({ decision: false, reason: false });
  const firstChoice = useRef<HTMLInputElement>(null);
  const reasonField = useRef<HTMLTextAreaElement>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = { decision: decision === null, reason: reason.trim() === '' };
    setErrors(found);
    if (found.decision) firstChoice.current?.focus();
    else if (found.reason) reasonField.current?.focus();
    else if (decision !== null) onDecide(decision, reason.trim());
  };

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('review.decision.heading')}</h2>
      <form className="alm-form" noValidate onSubmit={submit}>
        <fieldset className="alm-fieldset" aria-describedby={errors.decision ? `${id}-choice-error` : undefined}>
          <legend>{t('review.decision.legend')}</legend>
          {errors.decision ? <p id={`${id}-choice-error`} className="alm-field-error">{t('review.decision.choiceRequired')}</p> : null}
          {DECISIONS.map((kind, index) => (
            <label key={kind} className="alm-choice">
              <input
                ref={index === 0 ? firstChoice : undefined}
                type="radio"
                name={`${id}-decision`}
                value={kind}
                checked={decision === kind}
                onChange={() => setDecision(kind)}
              />
              {t(DECISION_KEYS[kind])}
            </label>
          ))}
        </fieldset>
        <div className="alm-field">
          <label htmlFor={`${id}-reason`}>{t('review.decision.reason')}</label>
          <p id={`${id}-reason-hint`} className="alm-muted">{t('review.decision.reasonHint')}</p>
          {errors.reason ? <p id={`${id}-reason-error`} className="alm-field-error">{t('review.decision.reasonRequired')}</p> : null}
          <textarea
            ref={reasonField}
            id={`${id}-reason`}
            className="alm-input"
            rows={3}
            value={reason}
            aria-invalid={errors.reason}
            aria-describedby={errors.reason ? `${id}-reason-hint ${id}-reason-error` : `${id}-reason-hint`}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <Button type="submit" busy={busy}>{t('review.decision.submit')}</Button>
      </form>
    </section>
  );
}
