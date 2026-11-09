import type { ButtonHTMLAttributes, MouseEvent } from 'react';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
  /** An action in progress: announced as busy, kept focusable, clicks ignored. */
  busy?: boolean;
}

export function Button({ variant = 'primary', busy = false, type = 'button', className, onClick, ...rest }: ButtonProps) {
  const classes = ['alm-button', variant === 'secondary' ? 'alm-button--secondary' : '', className ?? '']
    .filter(Boolean).join(' ');
  const click = (event: MouseEvent<HTMLButtonElement>) => {
    if (busy) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };
  return (
    <button
      {...rest}
      type={type}
      className={classes}
      onClick={click}
      {...(busy ? { 'aria-busy': true, 'aria-disabled': true } : {})}
    />
  );
}
