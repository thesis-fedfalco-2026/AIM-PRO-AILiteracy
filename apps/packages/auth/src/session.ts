import type { AuthoringClient } from '@alm/api-client';

/** The signed-in subject. The CSRF token lives only in memory, never in browser storage. */
export interface Session {
  subjectKey: string;
  csrfToken: string;
  expiresAt: Date;
}

export type SessionRead =
  | { status: 'signed-in'; session: Session }
  | { status: 'signed-out' }
  | { status: 'unmapped' };

/** An answer of the API the session flow does not expect. */
export class SessionError extends Error {
  constructor(readonly status: number) {
    super(`Session request failed with status ${status}`);
    this.name = 'SessionError';
  }
}

const LOGIN_PATH = '/auth/login';

/** Only a path on this site; anything that could leave it becomes `/` (as the API does). */
function localPath(value: string): string {
  return value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') ? value : '/';
}

/** The BFF login, which the browser opens as a page (D8): it ends with a redirect to `returnTo`. */
export function loginUrl(returnTo: string): string {
  return `${LOGIN_PATH}?${new URLSearchParams({ return_to: localPath(returnTo) })}`;
}

export interface SessionApi {
  readSession(): Promise<SessionRead>;
  /** Ends the API session; the result is the identity provider logout URL to open, if any. */
  signOut(csrfToken: string): Promise<string | null>;
}

export function createSessionApi(client: AuthoringClient): SessionApi {
  return {
    async readSession() {
      const { data, response } = await client.GET('/auth/session');
      if (data) {
        return {
          status: 'signed-in',
          session: { subjectKey: data.subject_key, csrfToken: data.csrf_token, expiresAt: new Date(data.expires_at) },
        };
      }
      if (response.status === 401) return { status: 'signed-out' };
      if (response.status === 403) return { status: 'unmapped' };
      throw new SessionError(response.status);
    },

    async signOut(csrfToken) {
      const { data, response } = await client.POST('/auth/logout', { headers: { 'X-CSRF-Token': csrfToken } });
      if (data) return data.end_session_url ?? null;
      if (response.status === 401) return null;
      throw new SessionError(response.status);
    },
  };
}
