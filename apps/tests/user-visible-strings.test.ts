import { describe, expect, it } from 'vitest';

import { componentFiles, hardCodedStrings, scanWorkspace } from '../scripts/user-visible-strings.mjs';

const texts = (source: string) => hardCodedStrings(source, 'Fixture.tsx').map((finding) => finding.text);

describe('user-visible strings', () => {
  it('are never hard-coded in the components of the workspace', async () => {
    expect(await scanWorkspace()).toEqual([]);
  });

  it('scan every component file of the packages and apps', async () => {
    const files = await componentFiles();
    expect(files.some((file) => file.startsWith('studio/src/'))).toBe(true);
    expect(files.some((file) => file.startsWith('packages/ui/src/'))).toBe(true);
    expect(files.every((file) => !file.includes('/test/'))).toBe(true);
  });

  it('flag JSX text, string children and visible attributes', () => {
    const source = `
      export function Bad({ name, ready }: { name: string; ready: boolean }) {
        return (
          <section aria-label="Main area" title={'Hint'}>
            <h1>Welcome back</h1>
            <p>{'Signed in as'} {name}</p>
            <p>{\`Hello \${name}\`}</p>
            <img alt="Logo" src="/logo.svg" />
            <input placeholder="Search" aria-description="Find things" />
            <Dialog label="Close" />
            <>{ready ? 'Ready' : name}{name && 'Named'}</>
          </section>
        );
      }`;
    expect(texts(source)).toEqual([
      'Main area', 'Hint', 'Welcome back', 'Signed in as', 'Hello ${…}', 'Logo', 'Search', 'Find things', 'Close', 'Ready', 'Named',
    ]);
  });

  it('report the file and line of each finding', () => {
    const [finding] = hardCodedStrings('const a = 1;\nexport const B = () => <b>Bold</b>;\n', 'B.tsx');
    expect(finding).toEqual({ file: 'B.tsx', line: 2, text: 'Bold' });
  });

  it('allow translated text, punctuation and non-visible attributes', () => {
    const source = `
      export function Good({ t, name }: { t: (key: string) => string; name: string }) {
        return (
          <main id="main" className="alm-shell" data-state="ready" aria-labelledby="title" role="status">
            <h1 id="title">{t('app.title')}</h1>
            <p>{name}{' '}·{' '}{t('session.signedIn', { name })}</p>
            <a href="#main" aria-label={t('shell.skip')}>{t('shell.skip')}</a>
            <span aria-hidden="true">→</span>
            <input type="text" autoComplete="off" />
          </main>
        );
      }`;
    expect(texts(source)).toEqual([]);
  });
});
