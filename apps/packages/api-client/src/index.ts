import createClient from 'openapi-fetch';

import type { components, paths } from './generated/authoring';

export type { components, paths } from './generated/authoring';

export type SessionView = components['schemas']['SessionView'];
export type LogoutView = components['schemas']['LogoutView'];
/** The body of every error response; `error` is a stable code, `request_id` correlates logs. */
export type ErrorBody = components['schemas']['ErrorBody'];

export type AuthoringClient = ReturnType<typeof createClient<paths>>;

export interface AuthoringClientOptions {
  /** Origin of the API; the browser apps use their own origin (D8: same-site cookie). */
  baseUrl: string;
  fetch?: (request: Request) => Promise<Response>;
}

/** The only way front-end modules reach the Authoring API. */
export function createAuthoringClient({ baseUrl, fetch }: AuthoringClientOptions): AuthoringClient {
  return createClient<paths>({
    baseUrl,
    credentials: 'same-origin',
    cache: 'no-store',
    ...(fetch ? { fetch } : {}),
  });
}
