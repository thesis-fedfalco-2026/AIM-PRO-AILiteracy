import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

import { expect, test as setup } from '@playwright/test';

import { ADMIN_STATE } from './stack/paths.mjs';
import { en } from './support';

// One real sign-in through the local Keycloak (D8): the BFF session cookie is kept
// for the tests. The API holds sessions in memory, so they last for one run.
setup('sign in as dev-admin through Keycloak', async ({ page }) => {
  await page.goto('/studio/');
  await page.getByRole('button', { name: en.session.signIn }).click();
  await page.locator('#username').fill('dev-admin');
  await page.locator('#password').fill(process.env.ALM_KEYCLOAK_DEV_PASSWORD ?? '');
  await page.locator('#kc-login').click();
  await expect(page.getByText(en.session.signedInAs.replace('{{subject}}', 'admin'))).toBeVisible();
  mkdirSync(dirname(ADMIN_STATE), { recursive: true });
  await page.context().storageState({ path: ADMIN_STATE });
});
