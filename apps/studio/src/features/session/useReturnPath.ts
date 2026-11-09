import { useHref, useLocation } from 'react-router';

/** The current studio address, with its base path, for the BFF login to return to. */
export function useReturnPath(): string {
  const { pathname, search } = useLocation();
  return useHref({ pathname, search });
}
