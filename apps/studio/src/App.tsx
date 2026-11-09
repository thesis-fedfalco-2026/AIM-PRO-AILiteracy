import { SessionProvider } from '@alm/auth';
import type { SessionApi } from '@alm/auth';
import type { i18n } from 'i18next';
import { I18nextProvider } from 'react-i18next';
import { RouterProvider } from 'react-router';
import type { createBrowserRouter } from 'react-router';

export interface StudioAppProps {
  api: SessionApi;
  router: ReturnType<typeof createBrowserRouter>;
  i18n: i18n;
  /** Full-page navigation to the BFF login and the provider logout; replaceable in tests. */
  navigate?: (url: string) => void;
}

export function StudioApp({ api, router, i18n, navigate }: StudioAppProps) {
  return (
    <I18nextProvider i18n={i18n}>
      <SessionProvider api={api} {...(navigate ? { navigate } : {})}>
        <RouterProvider router={router} />
      </SessionProvider>
    </I18nextProvider>
  );
}
