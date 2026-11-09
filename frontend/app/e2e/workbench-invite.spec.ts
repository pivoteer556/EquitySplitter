import { expect, Page, test } from '@playwright/test';
import { GOOD_PASSWORD, makeUser } from './helpers';

// Workbench owner invite against the REAL backend: the officer never types or sees an owner password, gets a
// one-time /accept-invite link instead, and the owner chooses their own password there.

async function signInOfficer(page: Page) {
  const officer = await makeUser('wb');
  await page.goto('/login');
  await page.locator('#login-email').fill(officer.email);
  await page.locator('#login-password').fill(officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page).toHaveURL(/\/workbench$/);
}

test('officer invites an owner: no password input, link shown, token not echoed, owner sets own password, link is single use', async ({
  page,
  browser,
}) => {
  await signInOfficer(page);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);

  await page.getByPlaceholder('Institution ID').fill(process.env['E2E_INSTITUTION_ID'] ?? '');
  await page.getByPlaceholder('Address').fill('1 Invite Street');
  await page.getByPlaceholder('Loan amount').fill('300000');
  await page.getByPlaceholder('Current balance').fill('250000');
  await page.getByPlaceholder('Monthly payment').fill('1500');
  await page.getByRole('button', { name: 'Create Property' }).click();
  await expect(page.getByText('propertyId: not set')).toHaveCount(0);

  const attached = page.waitForResponse((r) => r.url().endsWith('/agreement') && r.request().method() !== 'GET');
  await page.getByRole('button', { name: 'Attach Agreement' }).click();
  expect((await attached).status()).toBeLessThan(300);

  const ownerEmail = `wb-owner-${Date.now()}-${Math.random().toString(36).slice(2)}@e2e.example.com`;
  await page.getByPlaceholder('Owner name').fill('Invited Owner');
  await page.getByPlaceholder('Owner email').fill(ownerEmail);
  await page.getByPlaceholder('Max ownership percent').fill('50');
  await page.getByRole('button', { name: 'Invite Owner' }).click();

  const link = page.locator('#invite-link');
  await expect(link).toContainText('/accept-invite#token=');
  const url = (await link.innerText()).trim();
  const token = url.split('#token=')[1];
  expect(token.length).toBeGreaterThan(20);

  // The raw token appears exactly once on the page (the link box): not in the Output panel, not in the owner list.
  // (refreshOwners() clears the Output panel after an invite, so also check the whole body, not just Output.)
  await expect(page.getByText(ownerEmail)).toBeVisible();
  const bodyText = await page.locator('body').innerText();
  expect(bodyText.split(token).length - 1).toBe(1);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);

  // A fresh browser context (the owner): the link works once and the owner picks the password.
  const ctx = await browser.newContext();
  const owner = await ctx.newPage();
  await owner.goto(url);
  await owner.locator('#invite-password').fill(GOOD_PASSWORD);
  await owner.locator('#invite-confirm').fill(GOOD_PASSWORD);
  const accepted = owner.waitForResponse('**/api/v1/auth/accept-invite');
  await owner.getByRole('button', { name: 'Set password' }).click();
  expect((await accepted).status()).toBe(200);
  // The owner is signed in (user token stored) and lands on a page they can open, not bounced to /login.
  await expect(owner).toHaveURL(/\/listings$/);
  await expect(owner).not.toHaveURL(/\/login/);
  await expect.poll(() => owner.evaluate(() => (localStorage.getItem('userToken') ?? '').length)).toBeGreaterThan(20);
  expect(await owner.evaluate(() => localStorage.getItem('institutionToken'))).toBeNull();
  await ctx.close();

  // Reusing the same link is refused.
  const ctx2 = await browser.newContext();
  const again = await ctx2.newPage();
  await again.goto(url);
  const resp = again.waitForResponse('**/api/v1/auth/accept-invite');
  await again.locator('#invite-password').fill('An0ther!Passw0rd#2');
  await again.locator('#invite-confirm').fill('An0ther!Passw0rd#2');
  await again.getByRole('button', { name: 'Set password' }).click();
  expect((await resp).status()).toBe(401);
  await expect(again.getByRole('alert')).toBeVisible();
  await expect(again).not.toHaveURL(/\/workbench$/);
  await ctx2.close();
});
