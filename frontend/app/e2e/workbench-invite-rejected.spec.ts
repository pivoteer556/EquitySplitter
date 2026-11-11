import { expect, test } from '@playwright/test';
import { completeEnrolment, makeUser } from './helpers';

// Regression guard against the REAL backend: an Invite Owner the backend rejects after authenticating (400 "Property
// agreement must be attached first") used to rotate the officer's token without returning it, so the next call failed
// with 401 "Token no longer active" and the interceptor sent the officer to /login.
test('a rejected Invite Owner does not end the officer session: a later Attach Agreement still succeeds', async ({ page }) => {
  const officer = await makeUser('wb-invite-rej');
  await page.goto('/login');
  await page.locator('#login-email').fill(officer.email);
  await page.locator('#login-password').fill(officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await completeEnrolment(page);
  await expect(page).toHaveURL(/\/workbench$/);

  const createResponse = () => page.waitForResponse((r) => r.url().endsWith('/properties') && r.request().method() === 'POST');
  const inviteResponse = () => page.waitForResponse((r) => r.url().endsWith('/owners') && r.request().method() === 'POST');
  const agreementResponse = () => page.waitForResponse((r) => r.url().endsWith('/agreement') && r.request().method() === 'POST');
  await page.getByPlaceholder('Institution ID').fill(process.env['E2E_INSTITUTION_ID'] ?? '');
  await page.getByPlaceholder('Address').fill('1 Rejected Invite Street');
  await page.getByPlaceholder('Loan amount').fill('300000');
  await page.getByPlaceholder('Current balance').fill('250000');
  await page.getByPlaceholder('Monthly payment').fill('1500');
  const created = createResponse();
  await page.getByRole('button', { name: 'Create Property' }).click();
  expect((await created).status()).toBe(201);

  // Token iat is per second: wait so the rejected call runs in a later second than the token the browser holds,
  // otherwise a rotation on the rejection would be invisible.
  await page.waitForTimeout(1100);

  // Rejected after authentication: no agreement is attached yet.
  await page.getByPlaceholder('Owner name').fill('Rejected Owner');
  await page.getByPlaceholder('Owner email').fill(`wb-rejected-${Date.now()}-${Math.random().toString(36).slice(2)}@e2e.example.com`);
  await page.getByPlaceholder('Max ownership percent').fill('50');
  const invited = inviteResponse();
  await page.getByRole('button', { name: 'Invite Owner' }).click();
  const rejected = await invited;
  expect(rejected.status()).toBe(400);
  expect(await rejected.text()).toContain('Property agreement must be attached first');

  // Token iat is per second: wait so a stale rotated token cannot hide behind the same-second window.
  await page.waitForTimeout(1100);

  const ok = agreementResponse();
  await page.getByRole('button', { name: 'Attach Agreement' }).click();
  expect((await ok).status()).toBe(201);
  await expect(page).toHaveURL(/\/workbench$/);
});
