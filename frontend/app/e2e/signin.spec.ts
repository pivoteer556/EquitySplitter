import { expect, test } from '@playwright/test';
import { alertBox, countLoginCalls, expectNoSession, fill, LOGIN_API, makeUser } from './helpers';

// Adversarial suite for Sign In, run against the REAL backend (throwaway database `equity_e2e`).
// Only tests labelled "fault injection" intercept /api/v1: they simulate failures a healthy backend
// cannot produce (network loss, HTML 500, slow responses, hostile `detail` strings).

type Win = { __pwned?: number; __leaks?: string[] };

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
});

const loginButton = (page: import('@playwright/test').Page) => page.getByRole('button', { name: 'Login' });

test('sign-in button uses the brand blue', async ({ page }) => {
  await expect(loginButton(page)).toHaveCSS('background-color', 'rgb(58, 95, 176)');
});

test.describe('client-side validation cannot be skipped by typing nothing useful', () => {
  test('empty submit sends no request and shows no session', async ({ page }) => {
    const calls = countLoginCalls(page);
    await loginButton(page).click();
    expect(await page.locator('#login-email').evaluate((e: HTMLInputElement) => e.validity.valueMissing)).toBe(true);
    expect(calls.count()).toBe(0);
    await expectNoSession(page);
  });

  test('whitespace-only email is not sent', async ({ page }) => {
    const calls = countLoginCalls(page);
    await fill(page, '     ', 'whatever');
    await loginButton(page).click();
    expect(calls.count()).toBe(0);
    await expectNoSession(page);
  });

  for (const bad of ['plain', 'a@', '@b.com', 'a b@c.com', 'a@@b.com', '"><script>x</script>']) {
    test(`malformed email ${JSON.stringify(bad)} is not sent`, async ({ page }) => {
      const calls = countLoginCalls(page);
      await fill(page, bad, 'whatever');
      await loginButton(page).click();
      expect(calls.count()).toBe(0);
      await expectNoSession(page);
    });
  }

  test('empty password with valid email is not sent', async ({ page }) => {
    const calls = countLoginCalls(page);
    await fill(page, 'someone@e2e.example.com', '');
    await loginButton(page).click();
    expect(calls.count()).toBe(0);
  });

  test('bypassing browser validation: real 422 is shown as a plain sentence, not raw JSON', async ({ page }) => {
    // Client validation is advisory. Disable it and send an email the real server rejects (422, list detail).
    await page.locator('#signin-form').evaluate((f: HTMLFormElement) => (f.noValidate = true));
    await fill(page, 'no-at-sign', 'whatever');
    const resp = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect((await resp).status()).toBe(422);
    await expect(alertBox(page)).toHaveText('Something went wrong. Please try again.');
    await expect(alertBox(page)).not.toContainText('loc');
    await expectNoSession(page);
  });
});

test.describe('real backend responses', () => {
  test('wrong password -> real 401 -> friendly message, no token, stays on /login', async ({ page }) => {
    const user = await makeUser('wrongpw');
    await fill(page, user.email, 'Wrong!Passw0rd#9');
    const resp = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect((await resp).status()).toBe(401);
    await expect(alertBox(page)).toHaveText('Incorrect email or password.');
    await expectNoSession(page);
    // Observation (documented): the password field keeps its value after a failed attempt.
    await expect(page.locator('#login-password')).toHaveValue('Wrong!Passw0rd#9');
  });

  test('unknown email -> real 401 "Invalid credentials" is mapped to the generic message', async ({ page }) => {
    await fill(page, `ghost-${Date.now()}@e2e.example.com`, 'Wrong!Passw0rd#9');
    const resp = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect((await resp).status()).toBe(401);
    await expect(alertBox(page)).toHaveText('Incorrect email or password.');
    await expectNoSession(page);
  });

  test('unknown email and wrong password show the same message (no account enumeration)', async ({ page }) => {
    const user = await makeUser('enum');
    await fill(page, user.email, 'Wrong!Passw0rd#9');
    await loginButton(page).click();
    await expect(alertBox(page)).toBeVisible();
    const known = await alertBox(page).innerText();
    await page.reload();
    await fill(page, `ghost-${Date.now()}@e2e.example.com`, 'Wrong!Passw0rd#9');
    await loginButton(page).click();
    await expect(alertBox(page)).toHaveText(known);
  });

  test('real 429 after the real failed-login threshold, even with the CORRECT password afterwards', async ({ page }) => {
    // Each login runs a deliberately slow password hash; 5 failures + 1 success sit near the 30 s default under load.
    test.slow();
    const user = await makeUser('lockout');
    for (let i = 0; i < 5; i++) {
      await fill(page, user.email, 'Wrong!Passw0rd#9');
      const r = page.waitForResponse(LOGIN_API);
      await loginButton(page).click();
      expect((await r).status()).toBe(401);
      await expect(loginButton(page)).toBeEnabled();
    }
    await fill(page, user.email, user.password);
    const resp = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect((await resp).status()).toBe(429);
    await expect(alertBox(page)).toHaveText('Too many attempts. Please wait a minute and try again.');
    await expectNoSession(page);
  });

  test('lockout is per email: a locked-out account does not lock out another user', async ({ page }) => {
    // Each login runs a deliberately slow password hash; 5 failures + 1 success sit near the 30 s default under load.
    test.slow();
    const victim = await makeUser('victim');
    const other = await makeUser('other');
    for (let i = 0; i < 5; i++) {
      await fill(page, victim.email, 'Wrong!Passw0rd#9');
      const r = page.waitForResponse(LOGIN_API);
      await loginButton(page).click();
      await r;
      await expect(loginButton(page)).toBeEnabled();
    }
    await fill(page, other.email, other.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
  });

  test('upper-cased email of a real user still signs in', async ({ page }) => {
    const user = await makeUser('casing');
    await fill(page, user.email.toUpperCase(), user.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
  });

  test('success: token stored, lands on /workbench', async ({ page }) => {
    const user = await makeUser('ok');
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
    const token = await page.evaluate(() => localStorage.getItem('institutionToken'));
    expect(token).toMatch(/^[\w-]+\.[\w-]+\.[\w-]+$/);
    expect(await page.evaluate(() => localStorage.getItem('institutionId'))).toBeTruthy();
    expect(await page.evaluate(() => localStorage.getItem('userToken'))).toBeNull();
  });

  test('the access token is never rendered into the DOM, even for a frame', async ({ page }) => {
    // The login page assigns the whole response to `lastResponse` and renders it in a <pre> just before navigating.
    await page.evaluate(() => {
      const w = window as unknown as Win;
      w.__leaks = [];
      new MutationObserver(() => {
        if (/eyJ[\w-]{10,}\./.test(document.body.innerHTML)) w.__leaks!.push('token in DOM');
      }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
    });
    const user = await makeUser('leak');
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
    expect(await page.evaluate(() => (window as unknown as Win).__leaks)).toEqual([]);
    await expect(page.locator('body')).not.toContainText('eyJ');
  });

  test('10,000-char wrong password and 10,000-char email are rejected cleanly', async ({ page }) => {
    const user = await makeUser('long');
    await fill(page, user.email, 'A'.repeat(10_000));
    const r = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect((await r).status()).toBe(401);
    await expect(alertBox(page)).toHaveText('Incorrect email or password.');
    await page.reload();
    await fill(page, 'a'.repeat(10_000) + '@e2e.example.com', 'x');
    const r2 = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect([401, 422]).toContain((await r2).status());
    await expect(alertBox(page)).toBeVisible();
    await expectNoSession(page);
  });

  test('correct password followed by junk is NOT accepted (no silent truncation)', async ({ page }) => {
    const user = await makeUser('trunc');
    await fill(page, user.email, user.password + 'x'.repeat(200));
    const r = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect((await r).status()).toBe(401);
    await expectNoSession(page);
  });

  test('injection strings as credentials are inert', async ({ page }) => {
    await page.locator('#signin-form').evaluate((f: HTMLFormElement) => (f.noValidate = true));
    await fill(page, `"'><img src=x onerror=window.__pwned=1>@e2e.example.com`, `' OR '1'='1`);
    const r = page.waitForResponse(LOGIN_API);
    await loginButton(page).click();
    expect([401, 403, 422]).toContain((await r).status());
    await expect(alertBox(page)).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as Win).__pwned)).toBeUndefined();
    expect(await page.locator('img[src="x"]').count()).toBe(0);
    await expectNoSession(page);
  });
});

test.describe('fault injection (responses a healthy backend cannot produce)', () => {
  test('fault injection: hostile HTML in server `detail` is rendered as text, never executed', async ({ page }) => {
    await page.route(LOGIN_API, (route) =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '<img src=x onerror=window.__pwned=1><script>window.__pwned=2</script>' }),
      }),
    );
    await fill(page, 'a@b.com', 'x');
    await loginButton(page).click();
    await expect(alertBox(page)).toContainText('<img src=x onerror=window.__pwned=1>');
    expect(await page.locator('img[src="x"]').count()).toBe(0);
    expect(await page.evaluate(() => (window as unknown as Win).__pwned)).toBeUndefined();
  });

  test('fault injection: 500 with an HTML body shows the generic message, not markup', async ({ page }) => {
    await page.route(LOGIN_API, (route) =>
      route.fulfill({ status: 500, contentType: 'text/html', body: '<html><body><h1>Traceback</h1>secret stack</body></html>' }),
    );
    await fill(page, 'a@b.com', 'x');
    await loginButton(page).click();
    await expect(alertBox(page)).toHaveText('Something went wrong. Please try again.');
    await expect(page.locator('body')).not.toContainText('Traceback');
    await expect(loginButton(page)).toBeEnabled();
  });

  test('fault injection: network abort shows "Can\'t reach the server", then the same form recovers', async ({ page }) => {
    let fail = true;
    await page.route(LOGIN_API, (route) => (fail ? route.abort('connectionrefused') : route.continue()));
    const user = await makeUser('net');
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(alertBox(page)).toHaveText("Can't reach the server. Check your connection and try again.");
    await expect(loginButton(page)).toBeEnabled();
    fail = false; // network recovers; the same form must work without a reload
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
  });

  test('fault injection: 200 with an undecodable token must not leave that token behind', async ({ page }) => {
    test.fail(true, 'Known defect: ApiService stores the token before decoding it; a malformed token stays in localStorage while an error is shown.');
    await page.route(LOGIN_API, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ accessToken: 'a.!!!.c' }) }),
    );
    await fill(page, 'a@b.com', 'x');
    await loginButton(page).click();
    await expect(alertBox(page)).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem('institutionToken'))).toBeNull();
  });

  test('fault injection: slow response, Enter-mashing and force-clicking fire exactly one request', async ({ page }) => {
    const user = await makeUser('double');
    const bodies: string[] = [];
    await page.route(LOGIN_API, async (route) => {
      bodies.push(route.request().postData() ?? '');
      const real = await route.fetch();
      await new Promise((r) => setTimeout(r, 1500));
      await route.fulfill({ response: real });
    });
    await fill(page, user.email, user.password);
    for (let i = 0; i < 6; i++) await page.locator('#login-password').press('Enter');
    await page.getByRole('button', { name: /Signing in|Login/ }).click({ force: true, noWaitAfter: true }).catch(() => undefined);
    await expect(page).toHaveURL(/\/workbench$/);
    expect(bodies).toHaveLength(1);
  });

  test('fault injection: editing fields while a slow login is pending signs in with the SUBMITTED credentials', async ({ page }) => {
    const user = await makeUser('edit');
    const sent: string[] = [];
    await page.route(LOGIN_API, async (route) => {
      sent.push(route.request().postData() ?? '');
      const real = await route.fetch();
      await new Promise((r) => setTimeout(r, 1200));
      await route.fulfill({ response: real });
    });
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(page.getByRole('button', { name: 'Signing in...' })).toBeVisible();
    await page.locator('#login-email').fill('someone-else@e2e.example.com'); // typed while pending
    await expect(page).toHaveURL(/\/workbench$/);
    expect(JSON.parse(sent[0]).email).toBe(user.email);
    expect(sent).toHaveLength(1);
  });

  test('fault injection: a slow failing login shows the spinner, then the error, and does not stay stuck', async ({ page }) => {
    await page.route(LOGIN_API, async (route) => {
      await new Promise((r) => setTimeout(r, 800));
      await route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Invalid credentials"}' });
    });
    await fill(page, 'a@b.com', 'x');
    await loginButton(page).click();
    await expect(page.getByRole('button', { name: 'Signing in...' })).toBeDisabled();
    await expect(alertBox(page)).toHaveText('Incorrect email or password.');
    await expect(loginButton(page)).toBeEnabled();
  });
});

test.describe('keyboard-only', () => {
  test('Tab order email -> password -> Login, Enter submits', async ({ page }) => {
    const user = await makeUser('kbd');
    await page.locator('#login-email').focus();
    await page.keyboard.type(user.email);
    await page.keyboard.press('Tab');
    await expect(page.locator('#login-password')).toBeFocused();
    await page.keyboard.type(user.password);
    await page.keyboard.press('Tab');
    await expect(loginButton(page)).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/workbench$/);
  });

  test('error is announced via role=alert and Enter in the password field retries', async ({ page }) => {
    const user = await makeUser('kbd2');
    await fill(page, user.email, 'Wrong!Passw0rd#9');
    await page.locator('#login-password').press('Enter');
    await expect(alertBox(page)).toHaveText('Incorrect email or password.');
    await page.locator('#login-password').fill(user.password);
    await page.locator('#login-password').press('Enter');
    await expect(page).toHaveURL(/\/workbench$/);
  });
});

test.describe('session and routing', () => {
  test('unauthenticated deep link to /workbench redirects to /login', async ({ page }) => {
    await page.goto('/workbench');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('blank / whitespace token in localStorage does not open /workbench', async ({ page }) => {
    await page.evaluate(() => localStorage.setItem('institutionToken', '   '));
    await page.goto('/workbench');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('unknown routes fall back to /login', async ({ page }) => {
    await page.goto('/no/such/page');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('tampered / garbage token: guard must not admit it', async ({ page }) => {
    test.fail(true, 'Known defect: authGuard only checks the token is non-empty, so any string opens the /workbench shell (API calls would still 401).');
    await page.evaluate(() => localStorage.setItem('institutionToken', 'garbage.token.value'));
    await page.goto('/workbench');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('logout clears the token and the back button cannot return to /workbench', async ({ page }) => {
    const user = await makeUser('logout');
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => localStorage.getItem('institutionToken'))).toBeNull();
    await page.goBack();
    await page.goForward().catch(() => undefined);
    await expect(page).not.toHaveURL(/\/workbench$/);
  });

  test('logout leaves nothing identifying behind in localStorage', async ({ page }) => {
    test.fail(true, 'Known defect: clearTokens() does not clear the `institutionId` key, so the institution id survives logout.');
    const user = await makeUser('residue');
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
    await page.getByRole('button', { name: 'Logout' }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  });

  test('a reload on /workbench with a real session keeps the session', async ({ page }) => {
    const user = await makeUser('reload');
    await fill(page, user.email, user.password);
    await loginButton(page).click();
    await expect(page).toHaveURL(/\/workbench$/);
    await page.reload();
    await expect(page).toHaveURL(/\/workbench$/);
  });
});

test('brand header shows on /login and on another route (/buyer)', async ({ page }) => {
  const header = page.locator('header.brand');
  await expect(header).toBeVisible();
  await expect(header.getByRole('img', { name: /EquitySplitter logo mark/ })).toBeVisible();
  await expect(header).toContainText('EquitySplitter');
  await page.goto('/buyer');
  await expect(header).toBeVisible();
});
