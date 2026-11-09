// Start the Authoring API for the browser tests on a new synthetic seed (D15).
//
//   ALM_OIDC_CLIENT_SECRET=... node e2e/stack/api.mjs
//
// Removes e2e/.state, builds the seed with `python -m tests.seed`, keeps a copy
// of its database for the tests to restore, and runs the API on 127.0.0.1:58001
// against the local Keycloak realm alm-dev (compose.identity.yml), as the
// "With the studio" smoke test in docs/architecture/role-applications.md does.

import { spawn, spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, rmSync } from 'node:fs';

import { API_PORT, DATABASE, ISSUER, PRISTINE, ROOT, SEED, STATE, STUDIO_URL, TELEMETRY_OFF, python } from './paths.mjs';

if (!process.env.ALM_OIDC_CLIENT_SECRET) {
  process.stderr.write('Set ALM_OIDC_CLIENT_SECRET to the secret the local Keycloak realm was started with.\n');
  process.exit(2);
}

rmSync(STATE, { recursive: true, force: true });
mkdirSync(STATE, { recursive: true });
const seed = spawnSync(python(), ['-m', 'tests.seed', '--output', SEED], {
  cwd: ROOT, stdio: 'inherit', env: { ...process.env, ...TELEMETRY_OFF },
});
if (seed.status !== 0) process.exit(seed.status ?? 1);
copyFileSync(DATABASE, PRISTINE);

const api = spawn(python(), ['-m', 'services.authoring_api', '--port', String(API_PORT)], {
  cwd: ROOT,
  stdio: 'inherit',
  env: {
    ...process.env,
    ...TELEMETRY_OFF,
    ALM_OIDC_ISSUER: ISSUER,
    ALM_OIDC_CLIENT_ID: 'alm-authoring-api',
    ALM_OIDC_REDIRECT_URI: `${STUDIO_URL}/auth/callback`,
    ALM_OIDC_POST_LOGOUT_REDIRECT_URI: `${STUDIO_URL}/`,
    ALM_IDENTITY_MAP: `${ROOT}infra/keycloak/identity-map.dev.json`,
    ALM_API_COOKIE_SECURE: 'false',
    ALM_STORE: DATABASE,
    ALM_POLICY_DIR: `${SEED}policies`,
    ALM_JOBS_STORE: `${STATE}jobs.sqlite`,
  },
});
for (const signal of /** @type {const} */ (['SIGINT', 'SIGTERM'])) process.on(signal, () => api.kill(signal));
api.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
