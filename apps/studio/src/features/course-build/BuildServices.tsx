import { createContext, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';

import type { BuildApi } from './buildApi';

interface BuildServicesValue {
  api: BuildApi;
  /** Milliseconds between two reads of a running job. */
  pollMs: number;
  /** A new client request id: a retry of the same step reuses it, so the API replays instead of repeating. */
  newRequestId(): string;
}

const BuildServicesContext = createContext<BuildServicesValue | null>(null);

export function BuildServicesProvider({ api, pollMs = 1000, newRequestId, children }: {
  api: BuildApi; pollMs?: number; newRequestId?: () => string; children: ReactNode;
}) {
  const value = useMemo(() => ({ api, pollMs, newRequestId: newRequestId ?? (() => crypto.randomUUID()) }),
    [api, pollMs, newRequestId]);
  return <BuildServicesContext.Provider value={value}>{children}</BuildServicesContext.Provider>;
}

export function useBuildServices(): BuildServicesValue {
  const value = useContext(BuildServicesContext);
  if (!value) throw new Error('useBuildServices needs a BuildServicesProvider');
  return value;
}
