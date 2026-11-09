import { useSession } from '@alm/auth';
import { createContext, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';

import type { EntityRef, ReviewApi } from './reviewApi';

/**
 * One operation id per application of an approved proposal revision, kept in
 * memory for the life of the page: a retry after a lost answer sends the same id,
 * so the API replays the change instead of applying it twice (S06).
 */
export class OperationIds {
  private readonly ids = new Map<string, string>();

  constructor(private readonly create: () => string = () => crypto.randomUUID()) {}

  for(contextId: string, proposal: EntityRef): string {
    const key = JSON.stringify([contextId, proposal.type, proposal.id, proposal.version]);
    let id = this.ids.get(key);
    if (id === undefined) {
      id = this.create();
      this.ids.set(key, id);
    }
    return id;
  }
}

interface ReviewServicesValue {
  api: ReviewApi;
  operations: OperationIds;
}

const ReviewServicesContext = createContext<ReviewServicesValue | null>(null);

export function ReviewServicesProvider({ api, operations, children }: {
  api: ReviewApi; operations?: OperationIds; children: ReactNode;
}) {
  const value = useMemo(() => ({ api, operations: operations ?? new OperationIds() }), [api, operations]);
  return <ReviewServicesContext.Provider value={value}>{children}</ReviewServicesContext.Provider>;
}

export function useReviewServices(): ReviewServicesValue {
  const value = useContext(ReviewServicesContext);
  if (!value) throw new Error('useReviewServices needs a ReviewServicesProvider');
  return value;
}

/** The CSRF token of the signed-in session; review pages are shown only inside a signed-in shell. */
export function useCsrfToken(): string {
  const { state } = useSession();
  if (state.status !== 'signed-in') throw new Error('Review pages need a signed-in session');
  return state.session.csrfToken;
}
