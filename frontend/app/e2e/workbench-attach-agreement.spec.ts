import { expect, test } from '@playwright/test';
import { completeEnrolment, makeUser } from './helpers';

// Regression guard against the REAL backend: a second Attach Agreement the backend rejects after authenticating (409
// "Agreement already exists") used to rotate the officer's token without returning it, so the next call failed with
// 401 "Token no longer active" and the interceptor sent the officer to /login.
test('a rejected second Attach Agreement does not end the officer session: a later Create Property still succeeds', async ({ page }) => {
  const officer = await makeUser('wb-agreement');
  await page.goto('/login');
  await page.locator('#login-email').fill(officer.email);
  await page.locator('#login-password').fill(officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await completeEnrolment(page);
  await expect(page).toHaveURL(/\/workbench$/);

  const createResponse = () => page.waitForResponse((r) => r.url().endsWith('/properties') && r.request().method() === 'POST');
  const agreementResponse = () => page.waitForResponse((r) => r.url().endsWith('/agreement') && r.request().method() === 'POST');
  await page.getByPlaceholder('Institution ID').fill(process.env['E2E_INSTITUTION_ID'] ?? '');
  await page.getByPlaceholder('Address').fill('1 Agreement Street');
  await page.getByPlaceholder('Loan amount').fill('300000');
  await page.getByPlaceholder('Current balance').fill('250000');
  await page.getByPlaceholder('Monthly payment').fill('1500');
  const created = createResponse();
  await page.getByRole('button', { name: 'Create Property' }).click();
  expect((await created).status()).toBe(201);

  const first = agreementResponse();
  await page.getByRole('button', { name: 'Attach Agreement' }).click();
  expect((await first).status()).toBe(201);

  // Token iat is per second: wait so the rejected call runs in a later second than the token the browser holds,
  // otherwise a rotation on the 409 would be invisible.
  await page.waitForTimeout(1100);

  // Rejected after authentication: the property already has an agreement.
  const second = agreementResponse();
  await page.getByRole('button', { name: 'Attach Agreement' }).click();
  const rejected = await second;
  expect(rejected.status()).toBe(409);
  expect(await rejected.text()).toContain('Agreement already exists');

  // Token iat is per second: wait so a stale rotated token cannot hide behind the same-second window.
  await page.waitForTimeout(1100);

  await page.getByPlaceholder('Address').fill('2 Agreement Street');
  const ok = createResponse();
  await page.getByRole('button', { name: 'Create Property' }).click();
  expect((await ok).status()).toBe(201);
  await expect(page).toHaveURL(/\/workbench$/);
});
