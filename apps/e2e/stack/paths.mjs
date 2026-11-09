// Locations and settings shared by the browser-test stack and the tests.

import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/** Repository root: the Python modules (seed, API, CLI) run from here. */
export const ROOT = fileURLToPath(new URL('../../../', import.meta.url));
/** Everything a run writes; removed when the API starts. Ignored by git. */
export const STATE = fileURLToPath(new URL('../.state/', import.meta.url));
export const SEED = `${STATE}seed/`;
export const DATABASE = `${SEED}alm.sqlite`;
/** The seed database as built, copied back before each test. */
export const PRISTINE = `${STATE}pristine.sqlite`;
export const ADMIN_STATE = `${STATE}auth/admin.json`;
export const LEARNER_STATE = `${STATE}auth/learner.json`;

export const STUDIO_URL = 'http://127.0.0.1:58000';
export const API_PORT = 58001;
export const ISSUER = 'http://127.0.0.1:58080/realms/alm-dev';

/** The seed runs no model, but imports agent code: vendor telemetry stays off. */
export const TELEMETRY_OFF = { LANGFUSE_ENABLED: 'false', CREWAI_DISABLE_TELEMETRY: 'true', CREWAI_TRACING_ENABLED: 'false' };

/** `ALM_PYTHON`, else the repository virtual environment, else `python3`. */
export function python() {
  if (process.env.ALM_PYTHON) return process.env.ALM_PYTHON;
  const venv = `${ROOT}.venv/bin/python`;
  return existsSync(venv) ? venv : 'python3';
}
