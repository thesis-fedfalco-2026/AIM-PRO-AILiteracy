import { useSession } from '@alm/auth';
import { Button, StatusMessage } from '@alm/ui';
import { useId, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { useBuildServices } from '../build/BuildServices';
import { buildPath, coursePath, inboxPath } from '../review/paths';
import { ReviewError } from '../review/reviewApi';
import { useCsrfToken } from '../review/ReviewServices';

/** The id rule of the API: lowercase letters, digits and inner hyphens, at most 64 characters. */
const COURSE_ID = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;

/** Create a course: a new context in preparation, administered by the signed-in creator. */
function CreateCourse() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const id = useId();
  const { api } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { reload: reloadSession } = useSession();
  const [courseId, setCourseId] = useState('');
  const [invalid, setInvalid] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    const value = courseId.trim();
    const problem = value === '' ? t('home.courseRequired') : COURSE_ID.test(value) ? null : t('home.createInvalid');
    setInvalid(problem);
    setFailure(null);
    if (problem) return;
    setBusy(true);
    try {
      const course = await api.createCourse(csrfToken, value);
      void navigate(buildPath(course.context_id));
    } catch (error) {
      const reason = error instanceof ReviewError ? error.reason : 'failed';
      const detail = error instanceof ReviewError ? error.detail ?? '' : '';
      if (reason === 'signed-out') void reloadSession();
      else setFailure(reason === 'forbidden' ? t('home.createForbidden')
        : reason === 'conflict' ? t('home.createConflict', { detail })
          : reason === 'refused' ? t('home.createRefused', { detail }) : t('home.createFailed'));
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{t('home.createHeading')}</h2>
      <p>{t('home.createIntro')}</p>
      <form className="alm-form" noValidate onSubmit={(event) => void create(event)}>
        <div className="alm-field">
          <label htmlFor={`${id}-course`}>{t('home.courseLabel')}</label>
          <p id={`${id}-hint`} className="alm-muted">{t('home.courseHint')}</p>
          {invalid ? <p id={`${id}-error`} className="alm-field-error">{invalid}</p> : null}
          <input
            id={`${id}-course`}
            className="alm-input"
            type="text"
            autoComplete="off"
            spellCheck={false}
            value={courseId}
            aria-invalid={invalid !== null}
            aria-describedby={invalid ? `${id}-hint ${id}-error` : `${id}-hint`}
            onChange={(event) => setCourseId(event.target.value)}
          />
        </div>
        <Button type="submit" busy={busy}>{t('home.create')}</Button>
      </form>
      {failure ? <StatusMessage tone="error">{failure}</StatusMessage> : null}
    </section>
  );
}

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
      <CreateCourse />
    </>
  );
}
