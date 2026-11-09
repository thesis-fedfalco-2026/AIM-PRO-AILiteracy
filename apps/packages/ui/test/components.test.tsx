import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppShell, Button, StatusMessage } from '../src/index';

afterEach(cleanup);

describe('Button', () => {
  it('is a native button that does not submit forms by default', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    const button = screen.getByRole('button', { name: 'Go' });
    expect(button.getAttribute('type')).toBe('button');
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('marks a busy action and keeps it focusable', () => {
    render(<Button busy>Save</Button>);
    const button = screen.getByRole('button', { name: 'Save' });
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.hasAttribute('disabled')).toBe(false);
    expect(button.getAttribute('aria-disabled')).toBe('true');
  });

  it('ignores clicks while busy', () => {
    const onClick = vi.fn();
    render(<Button busy onClick={onClick}>Save</Button>);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('has a secondary variant', () => {
    render(<Button variant="secondary">Back</Button>);
    expect(screen.getByRole('button', { name: 'Back' }).className).toContain('alm-button--secondary');
  });
});

describe('AppShell', () => {
  const shell = () => render(
    <AppShell skipLinkLabel="Skip to content" title="Studio" headerActions={<Button>Out</Button>}>
      <h1>Page</h1>
    </AppShell>,
  );

  it('has banner and main landmarks with the content in main', () => {
    shell();
    expect(within(screen.getByRole('banner')).getByText('Studio')).toBeTruthy();
    expect(within(screen.getByRole('banner')).getByRole('button', { name: 'Out' })).toBeTruthy();
    expect(within(screen.getByRole('main')).getByRole('heading', { name: 'Page' })).toBeTruthy();
  });

  it('starts with a skip link to the main content (WCAG 2.4.1)', () => {
    shell();
    const links = screen.getAllByRole('link');
    const skip = links[0]!;
    expect(skip.textContent).toBe('Skip to content');
    const main = screen.getByRole('main');
    expect(skip.getAttribute('href')).toBe(`#${main.id}`);
    expect(main.getAttribute('tabindex')).toBe('-1');
  });
});

describe('StatusMessage', () => {
  it('announces information politely', () => {
    render(<StatusMessage>Loading</StatusMessage>);
    expect(screen.getByRole('status').textContent).toBe('Loading');
  });

  it('announces errors as alerts', () => {
    render(<StatusMessage tone="error">Failed</StatusMessage>);
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toBe('Failed');
    expect(alert.className).toContain('alm-status--error');
  });
});
