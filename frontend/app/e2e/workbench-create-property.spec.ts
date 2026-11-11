import { expect, test } from '@playwright/test';
import { completeEnrolment, makeUser } from './helpers';

// Regression guard against the REAL backend: a Create Property the backend rejects after authenticating (403, an
// institution that is not the officer's) used to rotate the officer's token without returning it, so the next call
// failed with 401 "Token no longer active" and the interceptor sent the officer to /login.
test('a rejected Create Property does not end the officer session: a second valid one still succeeds', async ({ page }) => {
  const officer = await makeUser('wb-create');
  await page.goto('/login');
  await page.locator('#login-email').fill(officer.email);
  await page.locator('#login-password').fill(officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await completeEnrolment(page);
  await expect(page).toHaveURL(/\/workbench$/);

  const createResponse = () => page.waitForResponse((r) => r.url().endsWith('/properties') && r.request().method() === 'POST');
  await page.getByPlaceholder('Address').fill('1 Rotation Street');
  await page.getByPlaceholder('Loan amount').fill('300000');
  await page.getByPlaceholder('Current balance').fill('250000');
  await page.getByPlaceholder('Monthly payment').fill('1500');

  // Rejected after authentication: a well-formed institution id that is not the officer's.
  await page.getByPlaceholder('Institution ID').fill('00000000-0000-4000-8000-000000000000');
  const rejected = createResponse();
  await page.getByRole('button', { name: 'Create Property' }).click();
  expect((await rejected).status()).toBe(403);

  // Token iat is per second: wait so a stale rotated token cannot hide behind the same-second window.
  await page.waitForTimeout(1100);

  await page.getByPlaceholder('Institution ID').fill(process.env['E2E_INSTITUTION_ID'] ?? '');
  const ok = createResponse();
  await page.getByRole('button', { name: 'Create Property' }).click();
  expect((await ok).status()).toBe(201);
  await expect(page.getByText('propertyId: not set')).toHaveCount(0);
  await expect(page).toHaveURL(/\/workbench$/);
});
