import type { RouteObject } from 'react-router';

import { HomePage } from './features/home/HomePage';
import { NotFoundPage } from './shell/NotFoundPage';
import { StudioShell } from './shell/StudioShell';

export { STUDIO_BASENAME } from './base';

/** Each feature adds its routes here; a module that is off has no route and no navigation entry. */
export const studioRoutes: RouteObject[] = [
  {
    path: '/',
    element: <StudioShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
