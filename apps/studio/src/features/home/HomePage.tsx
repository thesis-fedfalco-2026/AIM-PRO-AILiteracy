import { Button } from '@alm/ui';
import { useId, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { coursePath, inboxPath } from '../review/paths';

export function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = useId();
  const [contextId, setContextId] = useState('');
  const [missing, setMissing] = useState(false);

  const go = (path: (contextId: string) => string) => {
    const value = contextId.trim();
    setMissing(value === '');
    if (value) void navigate(path(value));
  };
  const open = (event: FormEvent) => {
    event.preventDefault();
    go(coursePath);
  };

  return (
    <>
      <h1>{t('home.title')}</h1>
      <p>{t('home.intro')}</p>
      <section aria-labelledby={`${id}-heading`}>
        <h2 id={`${id}-heading`}>{t('home.openHeading')}</h2>
        <form className="alm-form" noValidate onSubmit={open}>
          <div className="alm-field">
            <label htmlFor={`${id}-context`}>{t('home.contextLabel')}</label>
            <p id={`${id}-hint`} className="alm-muted">{t('home.contextHint')}</p>
            {missing ? <p id={`${id}-error`} className="alm-field-error">{t('home.contextRequired')}</p> : null}
            <input
              id={`${id}-context`}
              className="alm-input"
              type="text"
              autoComplete="off"
              spellCheck={false}
              value={contextId}
              aria-invalid={missing}
              aria-describedby={missing ? `${id}-hint ${id}-error` : `${id}-hint`}
              onChange={(event) => setContextId(event.target.value)}
            />
          </div>
          <div className="alm-actions">
            <Button type="submit">{t('home.open')}</Button>
            <Button variant="secondary" onClick={() => go(inboxPath)}>{t('home.openReview')}</Button>
          </div>
        </form>
      </section>
    </>
  );
}
