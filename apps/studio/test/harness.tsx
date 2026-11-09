import { createAuthoringClient } from '@alm/api-client';
import { createSessionApi } from '@alm/auth';
import { render } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { vi } from 'vitest';

import { StudioApp } from '../src/App';
import { createReviewApi } from '../src/features/review/reviewApi';
import { OperationIds } from '../src/features/review/ReviewServices';
import { createStudioI18n } from '../src/i18n';
import { STUDIO_BASENAME, studioRoutes } from '../src/routes';

export const SESSION = { subject_key: 'admin', csrf_token: 'csrf-1', expires_at: '2026-11-09T10:00:00Z' };

/** A reply of the fake API: a status and a JSON body, or `network` for a request that gets no answer. */
export type Reply = { status: number; body?: unknown } | 'network';

/**
 * Render the studio over a fake API. Replies are queued per `METHOD /path`; a
 * request without a queued reply fails the test. Every request is recorded.
 */
export async function renderStudio(replies: Record<string, Reply[]>, path = '/studio/') {
  const requests: Request[] = [];
  const client = createAuthoringClient({
    baseUrl: 'http://studio.test',
    fetch: async (request: Request) => {
      requests.push(request.clone());
      const key = `${request.method} ${decodeURIComponent(new URL(request.url).pathname)}`;
      const reply = replies[key]?.shift();
      if (!reply) throw new Error(`Unexpected request ${key}`);
      if (reply === 'network') throw new TypeError('Failed to fetch');
      return Response.json(reply.body ?? { error: 'x', detail: 'x', request_id: 'r' }, { status: reply.status });
    },
  });
  const navigate = vi.fn();
  let next = 0;
  const operations = new OperationIds(() => `operation-${(next += 1)}`);
  const router = createMemoryRouter(studioRoutes, { basename: STUDIO_BASENAME, initialEntries: [path] });
  render(
    <StudioApp api={createSessionApi(client)} review={createReviewApi(client)} operations={operations}
      navigate={navigate} router={router} i18n={await createStudioI18n()} />,
  );
  return { navigate, requests, router };
}
