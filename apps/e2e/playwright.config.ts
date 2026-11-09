import { fileURLToPath } from 'node:url';

import { defineConfig, devices } from '@playwright/test';

import { ADMIN_STATE, API_PORT, STATE, STUDIO_URL } from './stack/paths.mjs';

// Browser tests of the studio on the synthetic seed (roadmap S07). They need the
// local Keycloak of compose.identity.yml and the same ALM_KEYCLOAK_DEV_PASSWORD
// and ALM_OIDC_CLIENT_SECRET it was started with; see docs/architecture/role-applications.md.
// The tests share one database, restored before each test, so they run one at a time.
const APPS = fileURLToPath(new URL('..', import.meta.url));

export default defineConfig({
  testDir: '.',
  outputDir: `${STATE}results`,
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI ? [['list'], ['html', { outputFolder: `${STATE}report`, open: 'never' }]] : 'list',
  globalSetup: './stack/identity-check.ts',
  use: { baseURL: STUDIO_URL, trace: 'retain-on-failure' },
  projects: [
    { name: 'sign-in', testMatch: /sign-in\.setup\.ts$/ },
    {
      name: 'chromium',
      testMatch: /\.spec\.ts$/,
      dependencies: ['sign-in'],
      use: { ...devices['Desktop Chrome'], storageState: ADMIN_STATE },
    },
  ],
  // A port already in use fails the run instead of testing another process.
  webServer: [
    {
      command: 'node e2e/stack/api.mjs',
      cwd: APPS,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 180_000,
      stdout: 'ignore',
    },
    {
      command: 'npm run build --workspace @alm/studio && npm run preview --workspace @alm/studio',
      cwd: APPS,
      url: `${STUDIO_URL}/studio/`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
