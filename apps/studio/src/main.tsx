import '@alm/ui/styles.css';

import { createAuthoringClient } from '@alm/api-client';
import { createSessionApi } from '@alm/auth';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter } from 'react-router';

import { StudioApp } from './App';
import { createBuildApi } from './features/build/buildApi';
import { createReviewApi } from './features/review/reviewApi';
import { createStudioI18n } from './i18n';
import { STUDIO_BASENAME, studioRoutes } from './routes';

const root = document.getElementById('root');
if (!root) throw new Error('The studio page has no #root element');

void createStudioI18n().then((i18n) => {
  document.documentElement.lang = i18n.language;
  const client = createAuthoringClient({ baseUrl: window.location.origin });
  const api = createSessionApi(client);
  const review = createReviewApi(client);
  const build = createBuildApi(client);
  const router = createBrowserRouter(studioRoutes, { basename: STUDIO_BASENAME });
  createRoot(root).render(
    <StrictMode>
      <StudioApp api={api} review={review} build={build} router={router} i18n={i18n} />
    </StrictMode>,
  );
});
