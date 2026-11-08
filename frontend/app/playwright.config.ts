import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig } from '@playwright/test';

// Browser: an already-installed one (no Playwright browser download). Locally Microsoft Edge ('msedge');
// CI can set E2E_BROWSER_CHANNEL=chrome, or E2E_BROWSER_PATH=<executable>.
const executablePath = process.env['E2E_BROWSER_PATH'];

// Safety guard: the dev frontend build must point at a local API, never a deployed one.
const envSource = readFileSync(resolve(__dirname, 'src/environments/environment.ts'), 'utf8');
const apiBase = /apiBaseUrl:\s*'([^']+)'/.exec(envSource)?.[1] ?? '';
if (!/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//.test(apiBase)) {
  throw new Error(`e2e refuses to run: dev apiBaseUrl is not local (${apiBase || 'not found'})`);
}

const repoRoot = resolve(__dirname, '..', '..');
const python = resolve(repoRoot, '.venv', 'Scripts', 'python.exe');
const databaseUrl = 'postgresql+psycopg://postgres:postgres@localhost:55432/equity_e2e';

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: true,
  // Every login runs a deliberately slow password hash on one shared backend; many workers starve each other
  // (load-dependent timeouts in earlier runs). Two keeps the suite fast enough and stable.
  workers: 2,
  forbidOnly: !!process.env['CI'],
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:4200',
    channel: executablePath ? undefined : (process.env['E2E_BROWSER_CHANNEL'] ?? 'msedge'),
    launchOptions: executablePath ? { executablePath } : {},
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      // Real backend on a throwaway database. Always started fresh (reuseExistingServer false) so the
      // database is recreated, migrated and the signup rate limit starts at zero on every run.
      command: `"${python}" frontend/app/e2e/reset-db.py && "${python}" -m alembic upgrade head && "${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: repoRoot,
      env: { DATABASE_URL: databaseUrl },
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run start',
      url: 'http://localhost:4200',
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
});
