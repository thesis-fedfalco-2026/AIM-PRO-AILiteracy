import { SessionProvider } from '@alm/auth';
import type { SessionApi } from '@alm/auth';
import type { i18n } from 'i18next';
import { I18nextProvider } from 'react-i18next';
import { RouterProvider } from 'react-router';
import type { createBrowserRouter } from 'react-router';

import type { ReviewApi } from './features/review/reviewApi';
import { ReviewServicesProvider } from './features/review/ReviewServices';
import type { OperationIds } from './features/review/ReviewServices';

export interface StudioAppProps {
  api: SessionApi;
  review: ReviewApi;
  /** Operation ids of applications; replaceable in tests. */
  operations?: OperationIds;
  router: ReturnType<typeof createBrowserRouter>;
  i18n: i18n;
  /** Full-page navigation to the BFF login and the provider logout; replaceable in tests. */
  navigate?: (url: string) => void;
}

export function StudioApp({ api, review, operations, router, i18n, navigate }: StudioAppProps) {
  return (
    <I18nextProvider i18n={i18n}>
      <SessionProvider api={api} {...(navigate ? { navigate } : {})}>
        <ReviewServicesProvider api={review} {...(operations ? { operations } : {})}>
          <RouterProvider router={router} />
        </ReviewServicesProvider>
      </SessionProvider>
    </I18nextProvider>
  );
}
