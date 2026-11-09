import { expect, Page, test } from '@playwright/test';
import { BOOTSTRAP_TOKEN } from './constants';
import { API, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD } from './global-setup';
import { GOOD_PASSWORD } from './helpers';

// Adversarial suite for the Bootstrap New Institution form (on its own /bootstrap page, reached by URL only), against the REAL backend (which requires
// X-Bootstrap-Token AND a signed-in platform admin; every failure is the same 404). The admin signs in through the
// unified sign-in on /login (BACKLOG 2n). The backend keeps ONE active token
// per user, so these tests run serially and each signs in fresh. The signup limiter allows 10/hour/IP and global-setup already used one, so keep the
// number of requests that reach the backend small.

const BOOTSTRAP_API = '**/api/v1/auth/institution/bootstrap';

test.describe.configure({ mode: 'serial' });

/** Real UI sign-in on /login (the user login runs first), then open /bootstrap by URL and fill the officer fields. */
async function signInAndOpen(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await expect(page).toHaveURL(/\/listings/);
  await page.goto('/bootstrap');
  await fillOfficer(page);
}

async function fillOfficer(page: Page) {
  await expect(page.getByRole('heading', { name: 'Bootstrap New Institution' })).toBeVisible();
  // The fields start empty (no demo defaults), so every test fills them.
  await page.getByLabel('Institution name').fill('Bootstrap E2E Lending');
  await page.getByLabel('Loan officer name').fill('Boot Officer');
  await page.getByLabel('Loan officer email').fill(`boot-${Date.now()}-${Math.random().toString(36).slice(2)}@e2e.example.com`);
}

/** An ordinary (non-admin) account in the users table, made through the real signup API from its own client IP. */
async function makeOrdinaryUser(): Promise<{ email: string; password: string }> {
  const email = `ordinary-${process.pid}-${Date.now()}@e2e.example.com`;
  const ip = `10.9.${Math.floor(Math.random() * 250) + 1}.${Math.floor(Math.random() * 250) + 1}`;
  const res = await fetch(`${API}/auth/register`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-forwarded-for': ip },
    body: JSON.stringify({ name: 'Ordinary', email, password: GOOD_PASSWORD, isPlatformAdmin: true }),
  });
  if (res.status !== 201 && res.status !== 200) throw new Error(`register failed: ${res.status}`);
  return { email, password: GOOD_PASSWORD };
}

const submit = (page: import('@playwright/test').Page) => page.getByRole('button', { name: 'Bootstrap Institution' });
const tokenInput = (page: import('@playwright/test').Page) => page.getByLabel('Setup token');

async function expectNothingLeaked(page: import('@playwright/test').Page, secret: string) {
  expect(await page.locator('input[name="setupToken"]').inputValue()).toBe('');
  expect(await page.content()).not.toContain(secret);
  const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
  expect(storage).not.toContain(secret);
}

test('setup token field is a required password input and an empty submit sends no request', async ({ page }) => {
  await signInAndOpen(page, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD);
  let calls = 0;
  page.on('request', (r) => {
    if (r.url().includes('/auth/institution/bootstrap')) calls++;
  });
  await expect(tokenInput(page)).toHaveAttribute('type', 'password');
  await expect(tokenInput(page)).toHaveAttribute('autocomplete', 'off');
  await submit(page).click();
  expect(await tokenInput(page).evaluate((e: HTMLInputElement) => e.validity.valueMissing)).toBe(true);
  expect(calls).toBe(0);
  await expect(page.locator('.activation')).toHaveCount(0);
});

test('a wrong token shows an error, no activation link, and the token is gone from the page', async ({ page }) => {
  await signInAndOpen(page, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD);
  const wrong = 'definitely-wrong-token';
  const seen: (string | undefined)[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/auth/institution/bootstrap')) seen.push(r.headers()['x-bootstrap-token']);
  });
  const resp = page.waitForResponse(BOOTSTRAP_API);
  await tokenInput(page).fill(wrong);
  await submit(page).click();
  expect((await resp).status()).toBe(404);
  await expect(page.getByRole('alert')).toHaveText('Not accepted. Sign in as platform admin and check the setup token.');
  await expect(page.locator('.activation')).toHaveCount(0);
  expect(seen).toEqual([wrong]);
  await expectNothingLeaked(page, wrong);
});

test('the right token creates the institution, shows the activation link, and the token is gone from the page', async ({ page }) => {
  await signInAndOpen(page, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD);
  const resp = page.waitForResponse(BOOTSTRAP_API);
  await tokenInput(page).fill(BOOTSTRAP_TOKEN);
  await submit(page).click();
  expect((await resp).status()).toBe(201);
  await expect(page.locator('.activation a')).toContainText('/activate#token=');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expectNothingLeaked(page, BOOTSTRAP_TOKEN);
});

test('the form starts empty and says a setup token is needed', async ({ page }) => {
  await signInAndOpen(page, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD);
  await page.reload();
  for (const label of ['Institution name', 'Loan officer name', 'Loan officer email']) {
    await expect(page.getByLabel(label)).toHaveValue('');
  }
  await expect(page.locator('#setup-note')).toContainText('requires a setup token');
  await expect(page).toHaveTitle('Equity Splitter');
});

test('the sign-in page does not show the bootstrap form and does not link to /bootstrap', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Sign In', exact: true })).toBeVisible();
  await expect(page.locator('#bootstrap-form')).toHaveCount(0);
  await expect(page.getByLabel('Setup token')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Bootstrap New Institution' })).toHaveCount(0);
  await expect(page.locator('a[href="/bootstrap"]')).toHaveCount(0);
});

test('with no session /bootstrap shows the sign-in message and no form', async ({ page }) => {
  await page.goto('/bootstrap');
  await expect(page.locator('#signin-needed')).toContainText('Sign in as platform admin');
  await expect(page.locator('#bootstrap-form')).toHaveCount(0);
  await expect(page.getByLabel('Setup token')).toHaveCount(0);
  await page.locator('#signin-needed a').click();
  await expect(page).toHaveURL(/\/login/);
});

test('an officer (institution) session is not a platform admin: no form on /bootstrap', async ({ page }) => {
  const { makeUser, fill } = await import('./helpers');
  const u = await makeUser('bootofficer');
  await page.goto('/login');
  await fill(page, u.email, u.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page).toHaveURL(/\/workbench/);
  await page.goto('/bootstrap');
  await expect(page.locator('#signin-needed')).toBeVisible();
  await expect(page.locator('#bootstrap-form')).toHaveCount(0);
});

test('a signed-in ordinary user with the RIGHT token is rejected with the same message and no institution', async ({ page }) => {
  const u = await makeOrdinaryUser(); // registration ignores any isPlatformAdmin it is sent
  await signInAndOpen(page, u.email, u.password);
  const resp = page.waitForResponse(BOOTSTRAP_API);
  await tokenInput(page).fill(BOOTSTRAP_TOKEN);
  await submit(page).click();
  expect((await resp).status()).toBe(404);
  await expect(page.getByRole('alert')).toHaveText('Not accepted. Sign in as platform admin and check the setup token.');
  await expect(page.locator('.activation')).toHaveCount(0);
  await expectNothingLeaked(page, BOOTSTRAP_TOKEN);
});
