import { defineProject } from 'vitest/config';

export default defineProject({
  test: { name: 'auth', environment: 'jsdom', include: ['test/**/*.test.{ts,tsx}'] },
});
