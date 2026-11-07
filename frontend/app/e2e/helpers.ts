import { expect, Page, Request } from '@playwright/test';
import { ADMIN_EMAIL, ADMIN_PASSWORD, API } from './global-setup';

export const LOGIN_API = '**/api/v1/auth/institution/login';
export const GOOD_PASSWORD = 'Str0ng!Passw0rd#1';

export interface TestUser {
  email: string;
  password: string;
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
  const login = await fetch(`${API}/auth/institution/login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });
  if (login.status !== 200) throw new Error(`admin login failed: ${login.status}`);
  const { accessToken } = await login.json();
  const email = `${tag}-${process.pid}-${Date.now()}-${counter++}@e2e.example.com`.toLowerCase();
  const res = await fetch(`${API}/institution-users`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({
      institutionId: process.env['E2E_INSTITUTION_ID'],
      name: `User ${tag}`,
      email,
      password: GOOD_PASSWORD,
    }),
  });
  if (res.status !== 201) throw new Error(`makeUser failed: ${res.status} ${await res.text()}`);
  return { email, password: GOOD_PASSWORD };
}

/** Counts POSTs that actually leave the browser for the login endpoint. */
export function countLoginCalls(page: Page): { count: () => number } {
  let n = 0;
  page.on('request', (r: Request) => {
    if (r.method() === 'POST' && r.url().endsWith('/auth/institution/login')) n++;
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
