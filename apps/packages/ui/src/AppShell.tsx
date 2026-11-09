import type { ReactNode } from 'react';

export interface AppShellProps {
  /** Application name shown in the banner. */
  title: ReactNode;
  /** Text of the link that skips to the main content (WCAG 2.4.1). */
  skipLinkLabel: string;
  headerActions?: ReactNode;
  children: ReactNode;
}

export const MAIN_ID = 'alm-main';

/** Page frame: skip link, banner and main landmark. All text comes from the app. */
export function AppShell({ title, skipLinkLabel, headerActions, children }: AppShellProps) {
  return (
    <>
      <a className="alm-skip-link" href={`#${MAIN_ID}`}>{skipLinkLabel}</a>
      <header className="alm-header">
        <p className="alm-header__title">{title}</p>
        {headerActions ? <div className="alm-header__actions">{headerActions}</div> : null}
      </header>
      <main id={MAIN_ID} className="alm-main" tabIndex={-1}>
        {children}
      </main>
    </>
  );
}
