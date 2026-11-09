import { createAuthoringClient } from '@alm/api-client';
import { createSessionApi } from '@alm/auth';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { StudioApp } from '../src/App';
import en from '../src/i18n/en.json';
import { createStudioI18n } from '../src/i18n';
import { STUDIO_BASENAME, studioRoutes } from '../src/routes';

const SESSION = { subject_key: 'admin', csrf_token: 'csrf-1', expires_at: '2026-11-09T10:00:00Z' };
const END_SESSION = 'http://127.0.0.1:58080/realms/alm-dev/protocol/openid-connect/logout?client_id=x';

type Reply = { status: number; body?: unknown };

async function renderStudio(replies: Record<string, Reply[]>, path = '/studio/') {
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
  const navigate = vi.fn();
  const router = createMemoryRouter(studioRoutes, { basename: STUDIO_BASENAME, initialEntries: [path] });
  render(<StudioApp api={createSessionApi(client)} navigate={navigate} router={router} i18n={await createStudioI18n()} />);
  return { navigate, requests };
}

afterEach(cleanup);

describe('studio shell', () => {
  it('offers sign-in when there is no session', async () => {
    const { navigate } = await renderStudio({ 'GET /auth/session': [{ status: 401 }] });
    const button = await screen.findByRole('button', { name: en.session.signIn });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(en.signIn.title);
    act(() => button.click());
    expect(navigate).toHaveBeenCalledWith('/auth/login?return_to=%2Fstudio%2F');
  });

  it('returns to the page that asked for sign-in', async () => {
    const { navigate } = await renderStudio({ 'GET /auth/session': [{ status: 401 }] }, '/studio/projects?view=all');
    const button = await screen.findByRole('button', { name: en.session.signIn });
    act(() => button.click());
    expect(navigate).toHaveBeenCalledWith('/auth/login?return_to=%2Fstudio%2Fprojects%3Fview%3Dall');
  });

  it('shows the signed-in subject in the banner', async () => {
    await renderStudio({ 'GET /auth/session': [{ status: 200, body: SESSION }] });
    const banner = await screen.findByRole('banner');
    await waitFor(() => expect(within(banner).getByText(en.session.signedInAs.replace('{{subject}}', 'admin'))).toBeTruthy());
    expect(within(screen.getByRole('main')).getByRole('heading', { level: 1 }).textContent).toBe(en.home.title);
  });

  it('signs out at the API with the CSRF token, then at the identity provider', async () => {
    const { navigate, requests } = await renderStudio({
      'GET /auth/session': [{ status: 200, body: SESSION }],
      'POST /auth/logout': [{ status: 200, body: { end_session_url: END_SESSION } }],
    });
    const button = await screen.findByRole('button', { name: en.session.signOut });
    await act(async () => button.click());
    expect(requests.at(-1)?.headers.get('X-CSRF-Token')).toBe('csrf-1');
    expect(navigate).toHaveBeenCalledWith(END_SESSION);
  });

  it('reports a refused sign-out', async () => {
    await renderStudio({
      'GET /auth/session': [{ status: 200, body: SESSION }],
      'POST /auth/logout': [{ status: 403 }],
    });
    const button = await screen.findByRole('button', { name: en.session.signOut });
    await act(async () => button.click());
    expect(screen.getByRole('alert').textContent).toBe(en.session.signOutFailed);
  });

  it('explains an identity that is not mapped to a policy subject', async () => {
    await renderStudio({ 'GET /auth/session': [{ status: 403 }] });
    expect((await screen.findByRole('alert')).textContent).toBe(en.session.unmapped);
    expect(screen.getByRole('button', { name: en.session.signInAgain })).toBeTruthy();
  });

  it('reports an unavailable API and retries', async () => {
    await renderStudio({ 'GET /auth/session': [{ status: 502 }, { status: 200, body: SESSION }] });
    expect((await screen.findByRole('alert')).textContent).toBe(en.session.unavailable);
    await act(async () => screen.getByRole('button', { name: en.session.retry }).click());
    expect(await screen.findByRole('button', { name: en.session.signOut })).toBeTruthy();
  });

  it('announces loading', async () => {
    await renderStudio({ 'GET /auth/session': [{ status: 401 }] });
    expect(screen.getByRole('status').textContent).toBe(en.session.loading);
    await screen.findByRole('button', { name: en.session.signIn });
  });

  it('has a not-found page inside the shell', async () => {
    await renderStudio({ 'GET /auth/session': [{ status: 200, body: SESSION }] }, '/studio/nowhere');
    expect((await screen.findByRole('heading', { level: 1 })).textContent).toBe(en.notFound.title);
    expect(screen.getByRole('link', { name: en.notFound.home }).getAttribute('href')).toBe('/studio/');
  });

  it('starts with a skip link and sets the document title from the catalogue', async () => {
    await renderStudio({ 'GET /auth/session': [{ status: 401 }] });
    await screen.findByRole('button', { name: en.session.signIn });
    expect(screen.getAllByRole('link')[0]?.textContent).toBe(en.shell.skipToContent);
    expect(document.title).toBe(en.app.title);
  });
});

describe('English catalogue', () => {
  it('holds only non-empty strings', () => {
    const values = (node: unknown): unknown[] =>
      typeof node === 'object' && node !== null ? Object.values(node).flatMap(values) : [node];
    const all = values(en);
    expect(all.length).toBeGreaterThan(0);
    for (const value of all) {
      expect(typeof value).toBe('string');
      expect((value as string).trim()).not.toBe('');
    }
  });

  it('is the only language and resolves every key used by the shell', async () => {
    const i18n = await createStudioI18n();
    expect(i18n.language).toBe('en');
    expect(i18n.t('app.title')).toBe(en.app.title);
    expect(i18n.t('session.signedInAs', { subject: 'learner' })).toBe('Signed in as learner');
  });
});
