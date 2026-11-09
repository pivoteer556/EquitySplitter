// Fixed setup token the e2e backend is started with (playwright.config.ts sets BOOTSTRAP_TOKEN to this value).
export const BOOTSTRAP_TOKEN = 'e2e-setup-token';
// The throwaway database the e2e backend runs on (playwright.config.ts) and global-setup seeds the platform admin in.
export const E2E_DATABASE_URL = 'postgresql+psycopg://postgres:postgres@localhost:55432/equity_e2e';
