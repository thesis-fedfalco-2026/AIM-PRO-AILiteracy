import { ISSUER } from './paths.mjs';

/** Fail early, with the fix, when the local Keycloak or its dev password is missing. */
export default async function identityCheck() {
  if (!process.env.ALM_KEYCLOAK_DEV_PASSWORD) {
    throw new Error('Set ALM_KEYCLOAK_DEV_PASSWORD to the dev-* password the local Keycloak was started with.');
  }
  try {
    const response = await fetch(`${ISSUER}/.well-known/openid-configuration`);
    if (!response.ok) throw new Error(`status ${response.status}`);
  } catch (error) {
    throw new Error(`The local Keycloak does not answer at ${ISSUER} (${String(error)}). `
      + 'Start it with: docker compose -f compose.identity.yml up -d --wait');
  }
}
