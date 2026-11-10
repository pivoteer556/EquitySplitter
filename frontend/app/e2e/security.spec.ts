import { expect, Page, test } from '@playwright/test';
import { API } from './global-setup';
import { countRequests, fill, makeUser, totpCode } from './helpers';

// Officer security page: regenerate recovery codes against the REAL backend.

const CODE = /[A-Z2-9]{5}-[A-Z2-9]{5}/g;

/** Enrols a fresh officer through the UI, lands on /security via the nav link. Returns what the tests need. */
async function enrolAndOpenSecurity(page: Page) {
  const officer = await makeUser('security');
  await page.goto('/login');
  await fill(page, officer.email, officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.locator('#enrol-form')).toBeVisible();
  const secret = (await page.locator('#enrol-secret').innerText()).trim();
  await page.locator('#enrol-code').fill(totpCode(secret));
  await page.getByRole('button', { name: 'Verify and sign in' }).click();
  await expect(page.locator('#recovery-codes')).toBeVisible();
  const oldCodes = (await page.locator('#recovery-codes').innerText()).match(CODE)!;
  expect(oldCodes).toHaveLength(8);
  await page.locator('#recovery-continue').click();
  await expect(page).toHaveURL(/\/workbench$/);
  await page.locator('#security-link').click();
  await expect(page).toHaveURL(/\/security$/);
  return { officer, secret, oldCodes };
}

const submit = async (page: Page, code: string) => {
  await page.locator('#security-code').fill(code);
  await page.locator('#security-submit').click();
};

/** A 6-digit code that is not valid in any step the server could accept. */
const wrongCode = (secret: string) => {
  const valid = [-2, -1, 0, 1, 2].map((o) => totpCode(secret, o));
  return ['000000', '111111', '222222'].find((c) => !valid.includes(c))!;
};

test('signed-out visit to /security goes to the sign-in page', async ({ page }) => {
  await page.goto('/security');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.locator('#security-form')).toHaveCount(0);
});

test('a wrong code shows an error and no recovery codes', async ({ page }) => {
  const { secret } = await enrolAndOpenSecurity(page);
  const regen = countRequests(page, '/auth/institution/totp/recovery-codes');
  await submit(page, wrongCode(secret));
  await expect(page.locator('#security-error')).toBeVisible();
  await expect(page.locator('#security-codes')).toHaveCount(0);
  expect(regen.count()).toBe(1);
});

// Regression: a rejected attempt on POST /auth/institution/totp/recovery-codes must not rotate the officer's stored
// session token (a 401 cannot carry X-Refreshed-Token, so the browser would be left holding a dead token).
test('after a wrong code the same session can still regenerate with a correct code', async ({ page }) => {
  const { secret } = await enrolAndOpenSecurity(page);
  await submit(page, wrongCode(secret));
  await expect(page.locator('#security-error')).toBeVisible();
  await page.waitForTimeout(1100); // tokens carry a per-second iat: within the same second the rotated token is identical and the bug hides
  await submit(page, totpCode(secret, 1));
  await expect(page.locator('#security-codes li')).toHaveCount(8);
});

test('a fresh code shows exactly 8 new codes once; the old codes die; a replayed code is refused', async ({ page }) => {
  const { officer, secret, oldCodes } = await enrolAndOpenSecurity(page);

  // The enrolment code (its step) is spent; the next step is valid within the server's window and not yet used.
  const code = totpCode(secret, 1);
  await submit(page, code);
  await expect(page.locator('#security-codes li')).toHaveCount(8);
  await expect(page.locator('#security-error')).toHaveCount(0);
  const newCodes = (await page.locator('#security-codes').innerText()).match(CODE)!;
  expect(new Set(newCodes).size).toBe(8);
  expect(newCodes.filter((c) => oldCodes.includes(c))).toHaveLength(0);

  // Old codes are dead, a new one signs in (generic 401 vs 200), through the real second step.
  const post = (path: string, body: unknown) =>
    fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const challenge = async () => (await (await post('/auth/login', officer)).json()).challengeToken as string;
  const old = await post('/auth/login/totp', { challengeToken: await challenge(), code: oldCodes[0] });
  expect(old.status).toBe(401);
  expect(await old.json()).toEqual({ detail: 'Invalid credentials' });
  const fresh = await post('/auth/login/totp', { challengeToken: await challenge(), code: newCodes[0] });
  expect(fresh.status).toBe(200);

  // The same code again is a replay: an error, and the codes from the first success are gone from the page.
  await submit(page, code);
  await expect(page.locator('#security-error')).toBeVisible();
  await expect(page.locator('#security-codes')).toHaveCount(0);
});
