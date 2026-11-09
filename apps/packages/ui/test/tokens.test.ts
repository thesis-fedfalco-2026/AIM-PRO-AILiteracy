import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { contrastRatio } from '../src/contrast';

const SOURCE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
const css = (name: string) => readFileSync(join(SOURCE, name), 'utf8');

function colourTokens(): Map<string, string> {
  const tokens = new Map<string, string>();
  for (const match of css('tokens.css').matchAll(/(--alm-color-[a-z-]+):\s*(#[0-9a-f]{6});/gi)) {
    tokens.set(match[1]!, match[2]!);
  }
  return tokens;
}

/** [foreground, background, minimum]: 4.5 for text (WCAG 1.4.3), 3 for focus and boundaries (1.4.11). */
const PAIRS: [string, string, number][] = [
  ['--alm-color-text', '--alm-color-background', 4.5],
  ['--alm-color-text', '--alm-color-surface', 4.5],
  ['--alm-color-text-muted', '--alm-color-background', 4.5],
  ['--alm-color-text-muted', '--alm-color-surface', 4.5],
  ['--alm-color-link', '--alm-color-background', 4.5],
  ['--alm-color-on-accent', '--alm-color-accent', 4.5],
  ['--alm-color-on-accent', '--alm-color-accent-hover', 4.5],
  ['--alm-color-accent', '--alm-color-background', 4.5],
  ['--alm-color-danger', '--alm-color-background', 4.5],
  ['--alm-color-danger', '--alm-color-danger-surface', 4.5],
  ['--alm-color-text', '--alm-color-danger-surface', 4.5],
  ['--alm-color-focus', '--alm-color-background', 3],
  ['--alm-color-focus', '--alm-color-surface', 3],
  ['--alm-color-border-strong', '--alm-color-background', 3],
];

describe('design tokens', () => {
  it('compute the WCAG contrast ratio', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 5);
    expect(contrastRatio('#777777', '#ffffff')).toBeCloseTo(4.48, 2);
  });

  it.each(PAIRS)('%s on %s meets %d:1', (foreground, background, minimum) => {
    const tokens = colourTokens();
    expect(tokens.get(foreground), foreground).toBeDefined();
    expect(tokens.get(background), background).toBeDefined();
    expect(contrastRatio(tokens.get(foreground)!, tokens.get(background)!)).toBeGreaterThanOrEqual(minimum);
  });

  it('give every interactive element a visible focus indicator', () => {
    const styles = css('styles.css');
    for (const selector of ['.alm-button:focus-visible', '.alm-skip-link:focus', 'a:focus-visible']) {
      expect(styles).toContain(selector);
    }
    expect(styles).toMatch(/outline:\s*3px solid var\(--alm-color-focus\)/);
  });

  it('respect reduced motion', () => {
    expect(css('styles.css')).toContain('@media (prefers-reduced-motion: reduce)');
  });
});
