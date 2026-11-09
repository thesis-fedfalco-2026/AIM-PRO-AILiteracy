import { useSession } from '@alm/auth';
import { useCallback, useEffect, useState } from 'react';

import { ReviewError } from './reviewApi';
import type { Inbox, ReviewFailure } from './reviewApi';
import { useReviewServices } from './ReviewServices';

export type InboxState =
  | { status: 'loading' }
  | { status: 'ready'; inbox: Inbox }
  | { status: 'error'; reason: ReviewFailure };

/**
 * The inbox of a context, read on mount and on `reload`. While it reloads nothing
 * of the previous read is shown, so no decision is taken on content that is being
 * replaced. An ended session sends the shell back to sign-in.
 */
export function useInbox(contextId: string) {
  const { api } = useReviewServices();
  const { reload: reloadSession } = useSession();
  const [state, setState] = useState<InboxState>({ status: 'loading' });
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    let current = true;
    api.inbox(contextId).then(
      (inbox) => current && setState({ status: 'ready', inbox }),
      (error: unknown) => {
        if (!current) return;
        const reason = error instanceof ReviewError ? error.reason : 'failed';
        if (reason === 'signed-out') void reloadSession();
        else setState({ status: 'error', reason });
      },
    );
    return () => {
      current = false;
    };
  }, [api, contextId, generation, reloadSession]);

  const reload = useCallback(() => {
    setState({ status: 'loading' });
    setGeneration((value) => value + 1);
  }, []);

  return { state, reload };
}
