import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    projects: [
      'packages/*',
      'studio',
      { test: { name: 'workspace', include: ['tests/**/*.test.ts'], environment: 'node' } },
    ],
  },
});
