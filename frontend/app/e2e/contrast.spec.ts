import { expect, Page, test } from '@playwright/test';
import { completeEnrolment, fill, GOOD_PASSWORD, makeUser, totpCode } from './helpers';

// WCAG AA contrast audit in a REAL browser, from the ACTUAL computed colours (not from the CSS source).
//   text (every visible text node's element, inputs, selects, placeholders, buttons, links, error/status boxes): 4.5:1
//   UI component boundary (input/select/button border or fill vs what surrounds it) and keyboard focus ring: 3:1
// The effective background is resolved by walking up the ancestors and compositing every translucent layer; any CSS
// colour syntax the browser reports (rgb, color(srgb), oklab, color-mix results ...) is normalised through a 1x1 canvas.
// The thresholds are the WCAG AA ones and must not be loosened to make a page pass.

const TEXT_MIN = 4.5;
const UI_MIN = 3;

type RGBA = [number, number, number, number];
type RGB = [number, number, number];

interface TextRec {
  sel: string;
  what: string;
  fg: RGBA;
  bg: RGB;
}
interface BoxRec {
  sel: string;
  border: RGBA | null; // null: no visible border
  fill: RGBA;
  surround: RGB;
}
interface FocusRec {
  sel: string;
  outline: RGBA | null;
  outlineOffset: number;
  shadows: RGBA[]; // solid (blur 0) box-shadow rings with positive spread
  surround: RGB;
  own: RGB;
}
interface Audit {
  texts: TextRec[];
  boxes: BoxRec[];
  focus: FocusRec | null;
  headerRule: { border: RGBA | null; page: RGB } | null;
}

/** Runs in the page. `scope` limits the sweep to one element (hover checks); `wantFocus` also reads the focused element. */
function collect(args: { scope: string | null; wantFocus: boolean }): Audit {
  const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!;
  const rgba = (css: string): RGBA => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = '#000';
    ctx.fillStyle = css; // the canvas parses every CSS colour syntax the browser supports; an unparseable value keeps #000
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const over = (top: RGBA, under: RGB): RGB => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])) as RGB;
  const bgOf = (start: Element | null): RGB => {
    const layers: RGBA[] = [];
    for (let e = start; e; e = e.parentElement) {
      const c = rgba(getComputedStyle(e).backgroundColor);
      if (c[3] > 0) {
        layers.push(c);
        if (c[3] >= 0.999) break;
      }
    }
    let acc: RGB = [255, 255, 255]; // canvas default
    for (const l of layers.reverse()) acc = over(l, acc);
    return acc;
  };
  const sel = (e: Element) => {
    const t = (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${typeof e.className === 'string' && e.className ? '.' + e.className.trim().replace(/\s+/g, '.') : ''}${t ? ' "' + t + '"' : ''}`;
  };
  const visible = (e: Element) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && (e as HTMLElement).checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
  };

  const scoped = args.scope ? document.querySelector(args.scope) : null;
  if (args.scope && !scoped) return { texts: [], boxes: [], focus: null, headerRule: null }; // nothing is focused (Tab left the page)
  const all = scoped ? [scoped] : Array.from(document.body.querySelectorAll('*'));
  const texts: TextRec[] = [];
  const boxes: BoxRec[] = [];
  for (const e of all) {
    if (e.closest('svg, script, style, option') || !visible(e) || e.closest(':disabled')) continue;
    const cs = getComputedStyle(e);
    const tag = e.tagName;
    const isField = tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA';
    const ownText = Array.from(e.childNodes).some((n) => n.nodeType === 3 && (n.textContent || '').trim() !== '');
    const type = (e as HTMLInputElement).type;
    const isCheck = tag === 'INPUT' && (type === 'checkbox' || type === 'radio');
    if (ownText || (isField && !isCheck)) {
      texts.push({ sel: sel(e), what: 'text', fg: rgba(cs.color), bg: bgOf(e) });
    }
    if ((tag === 'INPUT' || tag === 'TEXTAREA') && (e as HTMLInputElement).placeholder) {
      texts.push({ sel: sel(e), what: 'placeholder', fg: rgba(getComputedStyle(e, '::placeholder').color), bg: bgOf(e) });
    }
    if ((isField && !isCheck) || tag === 'BUTTON') {
      const bw = parseFloat(cs.borderTopWidth);
      const hasBorder = bw > 0 && cs.borderTopStyle !== 'none' && cs.borderTopStyle !== 'hidden';
      boxes.push({
        sel: sel(e),
        border: hasBorder ? rgba(cs.borderTopColor) : null,
        fill: rgba(cs.backgroundColor),
        surround: bgOf(e.parentElement),
      });
    }
  }

  let focus: FocusRec | null = null;
  const a = document.activeElement;
  if (args.wantFocus && a && a !== document.body) {
    const cs = getComputedStyle(a);
    const shadows: RGBA[] = [];
    // Computed box-shadow lists put the colour first: "rgb(..) 0px 0px 0px 3px". Split on top-level commas.
    for (const part of cs.boxShadow === 'none' ? [] : cs.boxShadow.split(/,(?![^(]*\))/)) {
      const len = part.match(/(-?[\d.]+)px/g)?.map((x) => parseFloat(x)) ?? [];
      const colour = part.replace(/(-?[\d.]+)px/g, '').replace('inset', '').trim();
      if (len.length >= 4 && len[2] === 0 && len[3] > 0) shadows.push(rgba(colour));
    }
    const hasOutline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
    focus = {
      sel: sel(a),
      outline: hasOutline ? rgba(cs.outlineColor) : null,
      outlineOffset: parseFloat(cs.outlineOffset) || 0,
      shadows,
      surround: bgOf(a.parentElement),
      own: bgOf(a),
    };
  }

  let headerRule: Audit['headerRule'] = null;
  const header = document.querySelector('header.brand');
  if (!args.scope && header) {
    const cs = getComputedStyle(header);
    const has = parseFloat(cs.borderBottomWidth) > 0 && cs.borderBottomStyle !== 'none';
    headerRule = { border: has ? rgba(cs.borderBottomColor) : null, page: bgOf(header.parentElement) };
  }
  return { texts, boxes, focus, headerRule };
}

// WCAG 2.x relative luminance and contrast ratio.
const lin = (v: number) => {
  const s = v / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
};
const lum = (c: RGB) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
const ratio = (a: RGB, b: RGB) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const flatten = (top: RGBA, under: RGB): RGB => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])) as RGB;
const hex = (c: RGB) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');

function judge(page: string, state: string, a: Audit, failures: string[]) {
  const seen = new Set<string>();
  const fail = (key: string, msg: string) => {
    if (seen.has(key)) return;
    seen.add(key);
    failures.push(`${page} [${state}] ${msg}`);
  };
  for (const t of a.texts) {
    const fg = flatten(t.fg, t.bg);
    const r = ratio(fg, t.bg);
    if (r < TEXT_MIN) fail(`${t.sel}/${t.what}`, `${t.what} ${t.sel}: ${r.toFixed(2)}:1 (${hex(fg)} on ${hex(t.bg)}, need ${TEXT_MIN})`);
  }
  for (const b of a.boxes) {
    // A control is identifiable if its border OR its fill reaches 3:1 against what surrounds it.
    const border = b.border ? ratio(flatten(b.border, b.surround), b.surround) : 0;
    const fill = b.fill[3] > 0 ? ratio(flatten(b.fill, b.surround), b.surround) : 0;
    if (Math.max(border, fill) < UI_MIN) {
      fail(`${b.sel}/box`, `control boundary ${b.sel}: border ${border.toFixed(2)}:1, fill ${fill.toFixed(2)}:1 on ${hex(b.surround)} (need ${UI_MIN})`);
    }
  }
  if (a.focus) {
    const f = a.focus;
    const against = (c: RGBA, bg: RGB) => ratio(flatten(c, bg), bg);
    const rings = [...(f.outline ? [f.outline] : []), ...f.shadows];
    // The ring is drawn outside the control; with no gap (offset <= 0) it also touches the control's own fill.
    const scores = rings.map((c) => Math.min(against(c, f.surround), f.outlineOffset > 0 || !f.outline ? 99 : against(c, f.own)));
    const best = scores.length ? Math.max(...scores) : 0;
    if (best < UI_MIN) {
      fail(`${f.sel}/focus`, `focus ring ${f.sel}: ${scores.length ? best.toFixed(2) + ':1' : 'NO ring'} on ${hex(f.surround)} (need ${UI_MIN})`);
    }
  }
  if (a.headerRule) {
    const h = a.headerRule;
    const r = h.border ? ratio(flatten(h.border, h.page), h.page) : 0;
    if (r < UI_MIN) fail('header', `header rule: ${r.toFixed(2)}:1 on ${hex(h.page)} (need ${UI_MIN})`);
  }
}

/** Audits the page as it is now: every text node, every control boundary, the header rule, the keyboard focus ring of every focusable
 *  element (real Tab presses, so :focus-visible applies to buttons) and the hover state of every enabled button. */
async function audit(page: Page, name: string, state: string, failures: string[]): Promise<void> {
  await page.mouse.move(0, 0);
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  judge(name, state, await page.evaluate(collect, { scope: null, wantFocus: false }), failures);

  const focusables = page.locator('a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), summary');
  const n = await focusables.count();
  let visibleCount = 0;
  for (let i = 0; i < n; i++) if (await focusables.nth(i).isVisible()) visibleCount++;
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    (document.activeElement as HTMLElement | null)?.blur();
  });
  for (let i = 0; i < visibleCount; i++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(() => document.activeElement === document.body)) break; // Tab left the page
    judge(name, 'focus', await page.evaluate(collect, { scope: '*:focus', wantFocus: true }), failures);
  }
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const buttons = page.locator('button:not([disabled])');
  for (let i = 0; i < (await buttons.count()); i++) {
    const b = buttons.nth(i);
    if (!(await b.isVisible())) continue;
    await b.evaluate((e) => e.setAttribute('data-audit', '1'));
    await b.hover();
    judge(name, state + ' hover', await page.evaluate(collect, { scope: '[data-audit]', wantFocus: false }), failures);
    await b.evaluate((e) => e.removeAttribute('data-audit'));
  }
  await page.mouse.move(0, 0);
}

function verdict(failures: string[]) {
  expect(failures, `${failures.length} contrast failure(s):\n${failures.join('\n')}`).toHaveLength(0);
}

async function signInUpToEnrolment(page: Page) {
  const officer = await makeUser('contrast');
  await page.goto('/login');
  await fill(page, officer.email, officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.locator('#enrol-form')).toBeVisible();
}

test('/login: sign-in form, invalid field, error box, create-account form', async ({ page }) => {
  const failures: string[] = [];
  await page.goto('/login');
  await audit(page, '/login', 'form', failures);

  await page.locator('summary').click();
  await expect(page.locator('#register-name')).toBeVisible();
  await audit(page, '/login', 'create-account open', failures);
  await page.locator('summary').click();

  // :user-invalid border (typed text that is not an email, then leave the field)
  await page.locator('#login-email').fill('not-an-email');
  await page.keyboard.press('Tab');
  await audit(page, '/login', 'invalid field', failures);

  // Real error box: a sign-in that fails.
  await fill(page, `nobody-${Date.now()}@e2e.example.com`, 'Wr0ng!Passw0rd#1');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await audit(page, '/login', 'error box', failures);
  verdict(failures);
});

test('/login: enrolment step and recovery codes', async ({ page }) => {
  const failures: string[] = [];
  await signInUpToEnrolment(page);
  await audit(page, '/login', 'enrolment', failures);
  const secret = (await page.locator('#enrol-secret').innerText()).trim();
  await page.locator('#enrol-code').fill(totpCode(secret));
  await page.getByRole('button', { name: 'Verify and sign in' }).click();
  await expect(page.locator('#recovery-codes')).toBeVisible();
  await audit(page, '/login', 'recovery codes', failures);
  verdict(failures);
});

test('/workbench: signed-in officer, forms, status text, output and error boxes', async ({ page }) => {
  const failures: string[] = [];
  const officer = await makeUser('contrast');
  await page.goto('/login');
  await fill(page, officer.email, officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  await completeEnrolment(page);
  await expect(page).toHaveURL(/\/workbench$/);
  await audit(page, '/workbench', 'initial', failures);

  await page.getByPlaceholder('Institution ID').fill(process.env['E2E_INSTITUTION_ID'] ?? '');
  await page.getByPlaceholder('Address').fill('1 Contrast Street');
  await page.getByPlaceholder('Loan amount').fill('300000');
  await page.getByPlaceholder('Current balance').fill('250000');
  await page.getByPlaceholder('Monthly payment').fill('1500');
  await page.getByRole('button', { name: 'Create Property' }).click();
  await expect(page.getByText('propertyId: not set')).toHaveCount(0);
  const attached = page.waitForResponse((r) => r.url().endsWith('/agreement') && r.request().method() !== 'GET');
  await page.getByRole('button', { name: 'Attach Agreement' }).click();
  await attached;
  await page.getByPlaceholder('Owner name').fill('Contrast Owner');
  await page.getByPlaceholder('Owner email').fill(`contrast-owner-${Date.now()}@e2e.example.com`);
  await page.getByPlaceholder('Max ownership percent').fill('50');
  await page.getByRole('button', { name: 'Invite Owner' }).click();
  await expect(page.locator('#invite-link')).toContainText('/accept-invite#token=');
  await page.getByRole('button', { name: 'Get Owners' }).click();
  await expect(page.locator('li', { hasText: 'signedAt' })).toBeVisible();
  await audit(page, '/workbench', 'invite link, owner list, output pre', failures);

  // Error box: an invalid owner email is rejected by the real API.
  await page.getByPlaceholder('Owner email').fill('not-an-email');
  await page.getByRole('button', { name: 'Invite Owner' }).click();
  await expect(page.locator('pre.error')).toBeVisible();
  await audit(page, '/workbench', 'error box', failures);
  verdict(failures);
});

test('/security: officer page, error box and new recovery codes', async ({ page }) => {
  const failures: string[] = [];
  const officer = await makeUser('contrast');
  await page.goto('/login');
  await fill(page, officer.email, officer.password);
  await page.getByRole('button', { name: 'Login' }).click();
  const secret = await completeEnrolment(page);
  await expect(page).toHaveURL(/\/workbench$/);
  await page.locator('#security-link').click();
  await expect(page).toHaveURL(/\/security$/);
  await audit(page, '/security', 'form', failures);

  await page.locator('#security-code').fill('000000');
  await page.locator('#security-submit').click();
  await expect(page.locator('#security-error')).toBeVisible();
  await audit(page, '/security', 'error box', failures);

  await page.waitForTimeout(1100); // per-second token iat, same as security.spec.ts
  await page.locator('#security-code').fill(totpCode(secret, 1));
  await page.locator('#security-submit').click();
  await expect(page.locator('#security-codes li')).toHaveCount(8);
  await audit(page, '/security', 'recovery codes', failures);
  verdict(failures);
});

test('/bootstrap: signed-out notice, form and error box', async ({ page }) => {
  const failures: string[] = [];
  await page.goto('/bootstrap');
  await expect(page.locator('#signin-needed')).toBeVisible();
  await audit(page, '/bootstrap', 'signed out', failures);

  // Any non-empty user token renders the form; the server's answer is stubbed so the error box is deterministic.
  await page.addInitScript(() => localStorage.setItem('userToken', 'contrast-test-token'));
  await page.route('**/api/v1/auth/institution/bootstrap', (r) => r.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not found"}' }));
  await page.goto('/bootstrap');
  await expect(page.locator('#bootstrap-form')).toBeVisible();
  await audit(page, '/bootstrap', 'form', failures);
  await page.getByLabel('Institution name').fill('Contrast Lending');
  await page.getByLabel('Loan officer name').fill('Casey Officer');
  await page.getByLabel('Loan officer email').fill('casey@example.com');
  await page.locator('#setup-token').fill('whatever');
  await page.getByRole('button', { name: 'Bootstrap Institution' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await audit(page, '/bootstrap', 'error box', failures);
  verdict(failures);
});

for (const [route, field, button] of [
  ['/activate', '#activate-password', 'Activate'],
  ['/accept-invite', '#invite-password', 'Set password'],
] as const) {
  test(`${route}: missing-token error box, form, and rejected-token error box`, async ({ page }) => {
    const failures: string[] = [];
    await page.goto(route);
    await expect(page.getByRole('alert')).toBeVisible();
    await audit(page, route, 'no token', failures);

    await page.goto(`${route}#token=not-a-real-token`);
    await page.reload();
    await expect(page.locator(field)).toBeVisible();
    await audit(page, route, 'form', failures);
    const confirm = field.replace('password', 'confirm');
    await page.locator(field).fill(GOOD_PASSWORD);
    await page.locator(confirm).fill(GOOD_PASSWORD);
    await page.getByRole('button', { name: button }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    await audit(page, route, 'error box', failures);
    verdict(failures);
  });
}
