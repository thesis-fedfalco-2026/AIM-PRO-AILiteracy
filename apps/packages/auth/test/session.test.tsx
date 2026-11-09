import { createAuthoringClient } from '@alm/api-client';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SessionError, SessionProvider, createSessionApi, loginUrl, useSession } from '../src/index';

const SESSION = { subject_key: 'admin', csrf_token: 'csrf-1', expires_at: '2026-11-09T10:00:00Z' };
const END_SESSION = 'http://127.0.0.1:58080/realms/alm-dev/protocol/openid-connect/logout?client_id=x';

type Reply = { status: number; body?: unknown };

function fakeApi(replies: Record<string, Reply[]>) {
  const requests: Request[] = [];
  const client = createAuthoringClient({
    baseUrl: 'http://studio.test',
    fetch: async (request: Request) => {
      requests.push(request);
      const key = `${request.method} ${new URL(request.url).pathname}`;
      const reply = replies[key]?.shift();
      if (!reply) throw new Error(`Unexpected request ${key}`);
      return Response.json(reply.body ?? { error: 'x', detail: 'x', request_id: 'r' }, { status: reply.status });
    },
  });
  return { api: createSessionApi(client), requests };
}

afterEach(cleanup);

describe('loginUrl', () => {
  it('starts the BFF login with a local return path', () => {
    expect(loginUrl('/studio/')).toBe('/auth/login?return_to=%2Fstudio%2F');
    expect(loginUrl('/studio/projects?x=1')).toBe('/auth/login?return_to=%2Fstudio%2Fprojects%3Fx%3D1');
  });

  it('never returns to another site', () => {
    for (const target of ['https://evil.test/', '//evil.test/', 'studio', '/\\evil.test']) {
      expect(loginUrl(target)).toBe('/auth/login?return_to=%2F');
    }
  });
});

describe('createSessionApi', () => {
  it('reads the signed-in subject and the CSRF token', async () => {
    const { api, requests } = fakeApi({ 'GET /auth/session': [{ status: 200, body: SESSION }] });
    expect(await api.readSession()).toEqual({
      status: 'signed-in',
      session: { subjectKey: 'admin', csrfToken: 'csrf-1', expiresAt: new Date('2026-11-09T10:00:00Z') },
    });
    expect(requests[0]?.credentials).toBe('same-origin');
  });

  it('maps 401 to signed out and 403 to an unmapped identity', async () => {
    const { api } = fakeApi({ 'GET /auth/session': [{ status: 401 }, { status: 403 }] });
    expect(await api.readSession()).toEqual({ status: 'signed-out' });
    expect(await api.readSession()).toEqual({ status: 'unmapped' });
  });

  it('raises a SessionError with the status for any other answer', async () => {
    const { api } = fakeApi({ 'GET /auth/session': [{ status: 502 }] });
    await expect(api.readSession()).rejects.toEqual(new SessionError(502));
  });

  it('signs out with the CSRF header and returns the provider logout URL', async () => {
    const { api, requests } = fakeApi({ 'POST /auth/logout': [{ status: 200, body: { end_session_url: END_SESSION } }] });
    expect(await api.signOut('csrf-1')).toBe(END_SESSION);
    expect(requests[0]?.headers.get('X-CSRF-Token')).toBe('csrf-1');
  });

  it('treats an already ended session as signed out and refuses other failures', async () => {
    const { api } = fakeApi({ 'POST /auth/logout': [{ status: 401 }, { status: 403 }] });
    expect(await api.signOut('csrf-1')).toBeNull();
    await expect(api.signOut('stale')).rejects.toEqual(new SessionError(403));
  });
});

function Probe() {
  const { state, signIn, signOut, reload } = useSession();
  return (
    <div>
      <output data-testid="status">{state.status}</output>
      <output data-testid="subject">{state.status === 'signed-in' ? state.session.subjectKey : ''}</output>
      <output data-testid="sign-out">{state.status === 'signed-in' && state.signOutFailed ? 'failed' : ''}</output>
      <button type="button" onClick={() => signIn('/studio/')}>in</button>
      <button type="button" onClick={() => void signOut()}>out</button>
      <button type="button" onClick={() => void reload()}>reload</button>
    </div>
  );
}

const status = () => screen.getByTestId('status').textContent;

describe('SessionProvider', () => {
  it('loads the session and keeps the CSRF token out of browser storage', async () => {
    const { api } = fakeApi({ 'GET /auth/session': [{ status: 200, body: SESSION }] });
    render(<SessionProvider api={api} navigate={vi.fn()}><Probe /></SessionProvider>);
    expect(status()).toBe('loading');
    await waitFor(() => expect(status()).toBe('signed-in'));
    expect(screen.getByTestId('subject').textContent).toBe('admin');
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).toBe('');
  });

  it('signs in by navigating to the BFF login', async () => {
    const navigate = vi.fn();
    const { api } = fakeApi({ 'GET /auth/session': [{ status: 401 }] });
    render(<SessionProvider api={api} navigate={navigate}><Probe /></SessionProvider>);
    await waitFor(() => expect(status()).toBe('signed-out'));
    act(() => screen.getByRole('button', { name: 'in' }).click());
    expect(navigate).toHaveBeenCalledWith('/auth/login?return_to=%2Fstudio%2F');
  });

  it('signs out at the API, then at the identity provider', async () => {
    const navigate = vi.fn();
    const { api, requests } = fakeApi({
      'GET /auth/session': [{ status: 200, body: SESSION }],
      'POST /auth/logout': [{ status: 200, body: { end_session_url: END_SESSION } }],
    });
    render(<SessionProvider api={api} navigate={navigate}><Probe /></SessionProvider>);
    await waitFor(() => expect(status()).toBe('signed-in'));
    await act(async () => screen.getByRole('button', { name: 'out' }).click());
    expect(requests.at(-1)?.headers.get('X-CSRF-Token')).toBe('csrf-1');
    expect(status()).toBe('signed-out');
    expect(navigate).toHaveBeenCalledWith(END_SESSION);
  });

  it('is signed out without a provider logout URL', async () => {
    const navigate = vi.fn();
    const { api } = fakeApi({
      'GET /auth/session': [{ status: 200, body: SESSION }],
      'POST /auth/logout': [{ status: 200, body: { end_session_url: null } }],
    });
    render(<SessionProvider api={api} navigate={navigate}><Probe /></SessionProvider>);
    await waitFor(() => expect(status()).toBe('signed-in'));
    await act(async () => screen.getByRole('button', { name: 'out' }).click());
    expect(status()).toBe('signed-out');
    expect(navigate).not.toHaveBeenCalled();
  });

  it('reports a failed sign-out and keeps the session', async () => {
    const { api } = fakeApi({
      'GET /auth/session': [{ status: 200, body: SESSION }],
      'POST /auth/logout': [{ status: 403 }],
    });
    render(<SessionProvider api={api} navigate={vi.fn()}><Probe /></SessionProvider>);
    await waitFor(() => expect(status()).toBe('signed-in'));
    await act(async () => screen.getByRole('button', { name: 'out' }).click());
    expect(status()).toBe('signed-in');
    expect(screen.getByTestId('subject').textContent).toBe('admin');
    expect(screen.getByTestId('sign-out').textContent).toBe('failed');
  });

  it('reports an unavailable API and loads again on reload', async () => {
    const { api } = fakeApi({ 'GET /auth/session': [{ status: 500 }, { status: 200, body: SESSION }] });
    render(<SessionProvider api={api} navigate={vi.fn()}><Probe /></SessionProvider>);
    await waitFor(() => expect(status()).toBe('error'));
    await act(async () => screen.getByRole('button', { name: 'reload' }).click());
    await waitFor(() => expect(status()).toBe('signed-in'));
  });
});
