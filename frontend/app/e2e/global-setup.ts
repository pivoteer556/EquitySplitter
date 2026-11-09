// One real signup (the signup limiter allows 10/hour/IP): bootstrap an institution + officer, then activate the
// officer. Each test then mints its own users through the authenticated API, which is not signup-limited.
// Bootstrap needs a signed-in platform admin, created the way the operator does: run the script against the e2e
// database, redeem the one-time link it prints, log in with the password chosen there.
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { BOOTSTRAP_TOKEN, E2E_DATABASE_URL } from './constants';

export const API = 'http://127.0.0.1:8000/api/v1';
export const ADMIN_EMAIL = 'admin@e2e.example.com';
export const ADMIN_PASSWORD = 'Adm1n!Passw0rd#e2e';
export const PLATFORM_ADMIN_EMAIL = 'platform-admin@e2e.example.com';
export const PLATFORM_ADMIN_PASSWORD = 'Pl4tform!Passw0rd#e2e';

/**
 * Runs `python -m scripts.create_platform_admin <email>` against the e2e database (no password is ever given to the
 * script), redeems the printed link through accept-invite and returns the admin's bearer token for the API.
 */
export async function platformAdminBearer(): Promise<string> {
  const repoRoot = resolve(__dirname, '..', '..', '..');
  const python = process.env['E2E_PYTHON'] ?? resolve(repoRoot, '.venv', 'Scripts', 'python.exe');
  const out = execFileSync(python, ['-m', 'scripts.create_platform_admin', PLATFORM_ADMIN_EMAIL], {
    cwd: repoRoot,
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL },
    encoding: 'utf8',
  });
  const token = /#token=(\S+)/.exec(out)?.[1];
  if (!token) throw new Error('e2e: create_platform_admin printed no link');
  const res = await fetch(`${API}/auth/accept-invite`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-forwarded-for': nextIp() },
    body: JSON.stringify({ token, password: PLATFORM_ADMIN_PASSWORD }),
  });
  if (res.status !== 200) throw new Error(`e2e platform admin accept-invite failed: ${res.status} ${await res.text()}`);
  return (await res.json()).accessToken;
}

export default async function globalSetup(): Promise<void> {
  const adminToken = await platformAdminBearer();
  const res = await fetch(`${API}/auth/institution/bootstrap`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-bootstrap-token': BOOTSTRAP_TOKEN,
      authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      institutionName: 'E2E Lending',
      officerName: 'E2E Admin',
      officerEmail: ADMIN_EMAIL,
    }),
  });
  if (res.status !== 201) throw new Error(`e2e bootstrap failed: ${res.status} ${await res.text()}`);
  const body = await res.json();
  process.env['E2E_INSTITUTION_ID'] = body.institution.id;
  // Officers have no password until they use the activation link; do that over the API with the admin password.
  const act = await activate(body.activationToken, ADMIN_PASSWORD);
  if (act.status !== 200) throw new Error(`e2e admin activation failed: ${act.status} ${await act.text()}`);
}

/**
 * POST /auth/institution/activate. That endpoint allows 10 attempts/hour/IP, far fewer than the suite needs, so the
 * e2e backend runs with TRUSTED_PROXY_HOPS=1 (playwright.config.ts) and every call claims a distinct client IP.
 */
export async function activate(token: string, password: string): Promise<Response> {
  return fetch(`${API}/auth/institution/activate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-forwarded-for': nextIp() },
    body: JSON.stringify({ token, password }),
  });
}

let ipCounter = 0;
function nextIp(): string {
  const n = (process.pid * 1000 + ipCounter++) % 65000;
  return `10.${(n >> 8) & 255}.${n & 255}.${Math.floor(Math.random() * 250) + 1}`;
}
