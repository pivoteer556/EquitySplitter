import { expect, Page, test } from '@playwright/test';
import { activate } from './global-setup';
import { alertBox, completeEnrolment, GOOD_PASSWORD, makePendingOfficer } from './helpers';

// /activate page against the REAL backend: an officer created without a password sets one through the link.

const INVALID = 'This activation link is invalid or has expired. Ask for a new one.';
const OTHER_PASSWORD = 'An0ther!Passw0rd#2';

/** Opens the link and waits for Angular to boot (it strips the fragment), so a click cannot hit the bare HTML form. */
async function open(page: Page, token: string) {
  await page.goto(`/activate#token=${token}`);
  await expect.poll(() => page.url()).not.toContain('#');
}

async function submit(page: Page, pw: string, confirm = pw) {
  await page.locator('#activate-password').fill(pw);
  await page.locator('#activate-confirm').fill(confirm);
  await page.getByRole('button', { name: 'Activate' }).click();
}

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.getByRole('button', { name: 'Login' }).click();
}

const institutionToken = (page: Page) => page.evaluate(() => localStorage.getItem('institutionToken'));

test('happy path: the link sets the password, lands on the workbench, and the password then signs in', async ({ page }) => {
  const { email, token } = await makePendingOfficer('act');
  await open(page, token);
  expect(page.url()).not.toContain(token); // fragment is stripped from the address bar
  await submit(page, GOOD_PASSWORD);
  await expect(page).toHaveURL(/\/workbench$/);
  expect(await institutionToken(page)).toBeTruthy();

  await page.evaluate(() => localStorage.clear());
  await signIn(page, email, GOOD_PASSWORD);
  await completeEnrolment(page); // the officer has no authenticator yet
  await expect(page).toHaveURL(/\/workbench$/);
});

test('an unactivated officer cannot sign in', async ({ page }) => {
  const { email } = await makePendingOfficer('unact');
  await signIn(page, email, GOOD_PASSWORD);
  await expect(alertBox(page)).toHaveText('Incorrect email or password.');
  expect(await institutionToken(page)).toBeNull();
});

test('replaying a used token fails and does not change the password', async ({ page }) => {
  const { email, token } = await makePendingOfficer('replay');
  expect((await activate(token, GOOD_PASSWORD)).status).toBe(200);
  await open(page, token);
  await submit(page, OTHER_PASSWORD);
  await expect(alertBox(page)).toHaveText(INVALID);
  expect(await institutionToken(page)).toBeNull();
  await signIn(page, email, OTHER_PASSWORD);
  await expect(alertBox(page)).toHaveText('Incorrect email or password.');
});

test('a garbage token is rejected with the generic sentence', async ({ page }) => {
  await open(page, 'not.a.token');
  await submit(page, GOOD_PASSWORD);
  await expect(alertBox(page)).toHaveText(INVALID);
});

test('no token: no form, only a message', async ({ page }) => {
  await page.goto('/activate');
  await expect(page.locator('form')).toHaveCount(0);
  await expect(alertBox(page)).toContainText('activation link');
});

test('weak password sent past browser validation is refused (400) and the token stays usable', async ({ page }) => {
  const { token } = await makePendingOfficer('weak');
  await open(page, token);
  await page.locator('form').evaluate((f: HTMLFormElement) => (f.noValidate = true));
  const resp = page.waitForResponse('**/api/v1/auth/institution/activate');
  await submit(page, 'weak');
  expect((await resp).status()).toBe(400);
  await expect(alertBox(page)).toBeVisible();
  expect(await institutionToken(page)).toBeNull();
  expect((await activate(token, GOOD_PASSWORD)).status).toBe(200); // not burned by the failed attempt
});

test('browser validation blocks a weak or mismatched password before any request', async ({ page }) => {
  const { token } = await makePendingOfficer('native');
  await open(page, token);
  let calls = 0;
  page.on('request', (r) => {
    if (r.url().endsWith('/auth/institution/activate')) calls++;
  });
  await submit(page, 'weak');
  await submit(page, GOOD_PASSWORD, GOOD_PASSWORD + 'x');
  expect(calls).toBe(0);
});

test('new-password input advertises the rule and the browser rejects weak values natively', async ({ page }) => {
  const { token } = await makePendingOfficer('advert');
  await open(page, token);
  let calls = 0;
  page.on('request', (r) => {
    if (r.url().endsWith('/auth/institution/activate')) calls++;
  });
  const pw = page.locator('#activate-password');
  await expect(pw).toHaveAttribute('autocomplete', 'new-password');
  await expect(pw).toHaveAttribute('minlength', '10');
  await expect(pw).toHaveAttribute('pattern', /\(\?=\.\*\[a-z\]\)/);
  await expect(pw).toHaveAttribute('passwordrules', /minlength: 10; required: lower; required: upper; required: digit; required: special;/);
  await expect(page.locator('#activate-confirm')).toHaveAttribute('autocomplete', 'new-password');
  for (const weak of ['Short1!', 'nouppercase1!']) {
    await pw.fill(weak);
    expect(await pw.evaluate((i: HTMLInputElement) => i.validity.valid)).toBe(false);
    await submit(page, weak);
  }
  await pw.fill(GOOD_PASSWORD);
  expect(await pw.evaluate((i: HTMLInputElement) => i.validity.valid)).toBe(true);
  expect(calls).toBe(0);
});
