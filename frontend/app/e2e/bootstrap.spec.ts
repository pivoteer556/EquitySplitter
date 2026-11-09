import { expect, test } from '@playwright/test';
import { BOOTSTRAP_TOKEN } from './constants';

// Adversarial suite for the Bootstrap New Institution form, against the REAL backend (which requires
// X-Bootstrap-Token). The signup limiter allows 10/hour/IP and global-setup already used one, so keep the
// number of requests that reach the backend small.

const BOOTSTRAP_API = '**/api/v1/auth/institution/bootstrap';

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Bootstrap New Institution' })).toBeVisible();
  // The fields start empty (no demo defaults), so every test fills them.
  await page.getByLabel('Institution name').fill('Bootstrap E2E Lending');
  await page.getByLabel('Loan officer name').fill('Boot Officer');
  await page.getByLabel('Loan officer email').fill(`boot-${Date.now()}-${Math.random().toString(36).slice(2)}@e2e.example.com`);
});

const submit = (page: import('@playwright/test').Page) => page.getByRole('button', { name: 'Bootstrap Institution' });
const tokenInput = (page: import('@playwright/test').Page) => page.getByLabel('Setup token');

async function expectNothingLeaked(page: import('@playwright/test').Page, secret: string) {
  expect(await page.locator('input[name="setupToken"]').inputValue()).toBe('');
  expect(await page.content()).not.toContain(secret);
  const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
  expect(storage).not.toContain(secret);
}

test('setup token field is a required password input and an empty submit sends no request', async ({ page }) => {
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
  const wrong = 'definitely-wrong-token';
  const seen: (string | undefined)[] = [];
  page.on('request', (r) => {
    if (r.url().includes('/auth/institution/bootstrap')) seen.push(r.headers()['x-bootstrap-token']);
  });
  const resp = page.waitForResponse(BOOTSTRAP_API);
  await tokenInput(page).fill(wrong);
  await submit(page).click();
  expect((await resp).status()).toBe(404);
  await expect(page.getByRole('alert')).toHaveText('Setup token not accepted.');
  await expect(page.locator('.activation')).toHaveCount(0);
  expect(seen).toEqual([wrong]);
  await expectNothingLeaked(page, wrong);
});

test('the right token creates the institution, shows the activation link, and the token is gone from the page', async ({ page }) => {
  const resp = page.waitForResponse(BOOTSTRAP_API);
  await tokenInput(page).fill(BOOTSTRAP_TOKEN);
  await submit(page).click();
  expect((await resp).status()).toBe(201);
  await expect(page.locator('.activation a')).toContainText('/activate#token=');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expectNothingLeaked(page, BOOTSTRAP_TOKEN);
});

test('the form starts empty and says a setup token is needed', async ({ page }) => {
  await page.reload();
  for (const label of ['Institution name', 'Loan officer name', 'Loan officer email']) {
    await expect(page.getByLabel(label)).toHaveValue('');
  }
  await expect(page.locator('#setup-note')).toContainText('requires a setup token');
  await expect(page).toHaveTitle('Equity Splitter');
});
