import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

import { expect, test as setup } from '@playwright/test';

import { ADMIN_STATE, LEARNER_STATE } from './stack/paths.mjs';
import { en } from './support';

// One real sign-in per subject through the local Keycloak (D8): the BFF session
// cookie is kept for the tests. The API holds sessions in memory, so they last for one run.
for (const [user, subject, state] of [['dev-admin', 'admin', ADMIN_STATE], ['dev-learner', 'learner', LEARNER_STATE]]) {
  setup(`sign in as ${user} through Keycloak`, async ({ page }) => {
    await page.goto('/studio/');
    await page.getByRole('button', { name: en.session.signIn }).click();
    await page.locator('#username').fill(user!);
    await page.locator('#password').fill(process.env.ALM_KEYCLOAK_DEV_PASSWORD ?? '');
    await page.locator('#kc-login').click();
    await expect(page.getByText(en.session.signedInAs.replace('{{subject}}', subject!))).toBeVisible();
    mkdirSync(dirname(state!), { recursive: true });
    await page.context().storageState({ path: state! });
  });
}
