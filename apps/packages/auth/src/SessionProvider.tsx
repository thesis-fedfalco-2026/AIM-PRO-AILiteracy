import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { loginUrl } from './session';
import type { Session, SessionApi } from './session';

export type SessionState =
  | { status: 'loading' }
  | { status: 'signed-in'; session: Session; signOutFailed: boolean }
  | { status: 'signed-out' }
  | { status: 'unmapped' }
  | { status: 'error' };

export interface SessionContextValue {
  state: SessionState;
  /** Opens the BFF login; the provider returns the browser to `returnTo`. */
  signIn(returnTo: string): void;
  signOut(): Promise<void>;
  reload(): Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export interface SessionProviderProps {
  api: SessionApi;
  /** Full-page navigation, replaceable in tests. */
  navigate?: (url: string) => void;
  children: ReactNode;
}

const assignLocation = (url: string) => window.location.assign(url);

export function SessionProvider({ api, navigate = assignLocation, children }: SessionProviderProps) {
  const [state, setState] = useState<SessionState>({ status: 'loading' });

  const reload = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const read = await api.readSession();
      setState(read.status === 'signed-in' ? { ...read, signOutFailed: false } : read);
    } catch {
      setState({ status: 'error' });
    }
  }, [api]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const signIn = useCallback((returnTo: string) => navigate(loginUrl(returnTo)), [navigate]);

  const signOut = useCallback(async () => {
    if (state.status !== 'signed-in') return;
    try {
      const endSessionUrl = await api.signOut(state.session.csrfToken);
      setState({ status: 'signed-out' });
      if (endSessionUrl) navigate(endSessionUrl);
    } catch {
      setState({ ...state, signOutFailed: true });
    }
  }, [api, navigate, state]);

  const value = useMemo(() => ({ state, signIn, signOut, reload }), [state, signIn, signOut, reload]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession needs a SessionProvider');
  return value;
}
