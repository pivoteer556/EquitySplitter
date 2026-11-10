import { createHmac } from 'node:crypto';
import { expect, Page, Request } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { activate, ADMIN_TOKEN_FILE, API } from './global-setup';

export const LOGIN_API = '**/api/v1/auth/login';
export const GOOD_PASSWORD = 'Str0ng!Passw0rd#1';

export interface TestUser {
  email: string;
  password: string;
}

/**
 * Calls the API as the e2e institution admin. Every use rotates that officer's token (the response carries the next
 * one) and a password login now needs an authenticator code, so the current token lives in a file all workers share.
 * A worker that read it just before another one used it gets a 401; callers retry.
 */
async function adminCall(path: string, body: unknown): Promise<Response> {
  const token = readFileSync(ADMIN_TOKEN_FILE, 'utf8').trim();
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  const next = res.headers.get('x-refreshed-token');
  if (next) writeFileSync(ADMIN_TOKEN_FILE, next);
  return res;
}

let counter = 0;
/** Creates a real institution user through the real API (unique email: the login limiter is per email). */
export async function makeUser(tag: string): Promise<TestUser> {
  // The backend keeps ONE active token per user, so parallel workers logging in as the admin invalidate each
  // other's token (401 "Token no longer active"). Re-login and retry.
  for (let attempt = 0; ; attempt++) {
    try {
      return await createUser(tag);
    } catch (e) {
      if (attempt >= 8 || !String(e).includes('401')) throw e;
      await new Promise((r) => setTimeout(r, 50 + Math.random() * 150));
    }
  }
}

async function createUser(tag: string): Promise<TestUser> {
  const email = `${tag}-${process.pid}-${Date.now()}-${counter++}@e2e.example.com`.toLowerCase();
  const res = await adminCall('/institution-users', { institutionId: process.env['E2E_INSTITUTION_ID'], name: `User ${tag}`, email });
  if (res.status !== 201) throw new Error(`makeUser failed: ${res.status} ${await res.text()}`);
  const act = await activate((await res.json()).activationToken, GOOD_PASSWORD);
  if (act.status !== 200) throw new Error(`makeUser activation failed: ${act.status} ${await act.text()}`);
  return { email, password: GOOD_PASSWORD };
}

/** Creates an officer but leaves them unactivated; returns the activation token for the /activate page tests. */
export async function makePendingOfficer(tag: string): Promise<{ email: string; token: string }> {
  for (let attempt = 0; ; attempt++) {
    try {
      const email = `${tag}-${process.pid}-${Date.now()}-${counter++}@e2e.example.com`.toLowerCase();
      const res = await adminCall('/institution-users', { institutionId: process.env['E2E_INSTITUTION_ID'], name: `User ${tag}`, email });
      if (res.status !== 201) throw new Error(`makePendingOfficer failed: ${res.status} ${await res.text()}`);
      return { email, token: (await res.json()).activationToken };
    } catch (e) {
      if (attempt >= 8 || !String(e).includes('401')) throw e;
      await new Promise((r) => setTimeout(r, 50 + Math.random() * 150));
    }
  }
}

/** Counts POSTs that actually leave the browser for the login endpoint. */
export function countLoginCalls(page: Page): { count: () => number } {
  let n = 0;
  page.on('request', (r: Request) => {
    if (r.method() === 'POST' && r.url().endsWith('/auth/login')) n++;
  });
  return { count: () => n };
}

/** Counts POSTs whose URL ends with `suffix`. */
export function countRequests(page: Page, suffix: string): { count: () => number } {
  let n = 0;
  page.on('request', (r: Request) => {
    if (r.method() === 'POST' && r.url().endsWith(suffix)) n++;
  });
  return { count: () => n };
}

export async function fill(page: Page, email: string, password: string): Promise<void> {
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
}

export const alertBox = (page: Page) => page.getByRole('alert');

export async function expectNoSession(page: Page): Promise<void> {
  expect(await page.evaluate(() => localStorage.getItem('institutionToken'))).toBeNull();
  expect(new URL(page.url()).pathname).toBe('/login');
}

/** RFC 6238 (SHA-1, 6 digits, 30 s) from a base32 secret, for the step `offset` steps from now. Uses node crypto only. */
export function totpCode(secretBase32: string, offset = 0): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of secretBase32.replace(/=+$/, '').toUpperCase()) bits += alphabet.indexOf(ch).toString(2).padStart(5, '0');
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30_000) + offset));
  const mac = createHmac('sha1', key).update(counter).digest();
  const o = mac[mac.length - 1] & 0x0f;
  return String((mac.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, '0');
}

/** Makes an officer and enrols + confirms TOTP through the real API (first sign-in flow). Returns the secret. The confirming code is spent. */
export async function makeTotpOfficer(tag: string): Promise<TestUser & { secret: string }> {
  const user = await makeUser(tag);
  const post = (path: string, body: unknown) =>
    fetch(`${API}${path}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const login = await post('/auth/login', user);
  const { challengeToken, enrolmentRequired } = await login.json(); // no credential yet, so this is the enrolment challenge
  if (!enrolmentRequired) throw new Error(`expected an enrolment challenge: ${login.status}`);
  const start = await post('/auth/login/totp/enroll-start', { challengeToken });
  if (start.status !== 200) throw new Error(`enroll-start failed: ${start.status}`);
  const { secret } = await start.json();
  const confirm = await post('/auth/login/totp/enroll-confirm', { challengeToken, code: totpCode(secret) });
  if (confirm.status !== 200) throw new Error(`enroll-confirm failed: ${confirm.status} ${await confirm.text()}`);
  return { ...user, secret };
}

/** UI: after Login on a never-enrolled officer, completes the enrolment step with a real code and clicks Continue past the recovery codes. Returns the secret. */
export async function completeEnrolment(page: Page): Promise<string> {
  await expect(page.locator('#enrol-secret')).toBeVisible();
  const secret = (await page.locator('#enrol-secret').innerText()).trim();
  await page.locator('#enrol-code').fill(totpCode(secret));
  await page.getByRole('button', { name: 'Verify and sign in' }).click();
  await page.locator('#recovery-continue').click();
  return secret;
}
