import { SessionProvider } from '@alm/auth';
import type { SessionApi } from '@alm/auth';
import type { i18n } from 'i18next';
import { I18nextProvider } from 'react-i18next';
import { RouterProvider } from 'react-router';
import type { createBrowserRouter } from 'react-router';

import type { BuildApi } from './features/course-build/buildApi';
import { BuildServicesProvider } from './features/course-build/BuildServices';
import type { ReviewApi } from './features/review/reviewApi';
import { ReviewServicesProvider } from './features/review/ReviewServices';
import type { OperationIds } from './features/review/ReviewServices';

export interface StudioAppProps {
  api: SessionApi;
  review: ReviewApi;
  build: BuildApi;
  /** Milliseconds between two reads of a running job, and new request ids; replaceable in tests. */
  pollMs?: number;
  newRequestId?: () => string;
  /** Operation ids of applications; replaceable in tests. */
  operations?: OperationIds;
  router: ReturnType<typeof createBrowserRouter>;
  i18n: i18n;
  /** Full-page navigation to the BFF login and the provider logout; replaceable in tests. */
  navigate?: (url: string) => void;
}

export function StudioApp({ api, review, build, pollMs, newRequestId, operations, router, i18n, navigate }: StudioAppProps) {
  return (
    <I18nextProvider i18n={i18n}>
      <SessionProvider api={api} {...(navigate ? { navigate } : {})}>
        <ReviewServicesProvider api={review} {...(operations ? { operations } : {})}>
          <BuildServicesProvider api={build} {...(pollMs === undefined ? {} : { pollMs })}
            {...(newRequestId ? { newRequestId } : {})}>
            <RouterProvider router={router} />
          </BuildServicesProvider>
        </ReviewServicesProvider>
      </SessionProvider>
    </I18nextProvider>
  );
}
