import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import { E2E_DATABASE_URL } from './constants';
import { GOOD_PASSWORD } from './helpers';

// /home against the REAL backend, seeded by the REAL operator script (scripts/seed_demo.py, the fictional demo house):
// a co-buyer redeems the one-time link the script prints, sets a password, signs in and sees the house, the owners and the terms.

const BUYER_EMAIL = 'marisol.vega@example.com';

test('a seeded co-buyer sets a password, signs in and sees the house, the owners and the purchase terms', async ({ page }) => {
  test.setTimeout(90_000); // the seed script, then two deliberately slow password hashes
  const repoRoot = resolve(__dirname, '..', '..', '..');
  const python = process.env['E2E_PYTHON'] ?? resolve(repoRoot, '.venv', 'Scripts', 'python.exe');
  const out = execFileSync(python, ['-m', 'scripts.seed_demo', '--yes'], {
    cwd: repoRoot,
    env: { ...process.env, DATABASE_URL: E2E_DATABASE_URL },
    encoding: 'utf8',
  });
  const token = /marisol\.vega@example\.com: \S+#token=(\S+)/.exec(out)?.[1];
  expect(token, 'seed_demo printed no setup link for the buyer').toBeTruthy();

  await page.goto(`/accept-invite#token=${token}`);
  await expect.poll(() => page.url()).not.toContain('#'); // Angular booted and stripped the fragment
  await page.locator('#invite-password').fill(GOOD_PASSWORD);
  await page.locator('#invite-confirm').fill(GOOD_PASSWORD);
  await page.getByRole('button', { name: 'Set password' }).click();
  await expect(page).toHaveURL(/\/listings$/);

  await page.evaluate(() => localStorage.clear());
  await page.goto('/login');
  await page.locator('#login-email').fill(BUYER_EMAIL);
  await page.locator('#login-password').fill(GOOD_PASSWORD);
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await expect(page).toHaveURL(/\/listings$/);

  await page.goto('/home');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('418 Larkspur Court');

  const owners = page.locator('table.owners tbody tr');
  await expect(owners).toHaveCount(3);
  const rows = [
    ['Marisol Vega', '50.00%', '$1,000.54'],
    ['Dev Raman', '31.25%', '$625.34'],
    ['Hana Lindqvist', '18.75%', '$375.20'],
  ];
  for (const [name, share, monthly] of rows) {
    const row = owners.filter({ hasText: name });
    await expect(row).toHaveCount(1);
    await expect(row.locator('td').nth(1)).toHaveText(share);
    await expect(row.locator('td').nth(2)).toHaveText(monthly);
  }

  const terms = page.locator('table.terms');
  await expect(terms.locator('tr', { hasText: 'Purchase price' })).toContainText('$485,000.00');
  await expect(terms.locator('tr', { hasText: 'Closing date' })).toContainText('Dec 18, 2026');
});
