import type { ReactNode } from 'react';

export interface StatusMessageProps {
  /** `info` is announced politely (`status`), `error` at once (`alert`). */
  tone?: 'info' | 'error';
  children: ReactNode;
}

export function StatusMessage({ tone = 'info', children }: StatusMessageProps) {
  return (
    <p role={tone === 'error' ? 'alert' : 'status'} className={`alm-status alm-status--${tone}`}>
      {children}
    </p>
  );
}
