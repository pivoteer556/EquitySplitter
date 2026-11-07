// One real signup (the signup limiter allows 10/hour/IP): bootstrap an institution + officer.
// Each test then mints its own users through the authenticated API, which is not signup-limited.
export const API = 'http://127.0.0.1:8000/api/v1';
export const ADMIN_EMAIL = 'admin@e2e.example.com';
export const ADMIN_PASSWORD = 'Adm1n!Passw0rd#e2e';

export default async function globalSetup(): Promise<void> {
  const res = await fetch(`${API}/auth/institution/bootstrap`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      institutionName: 'E2E Lending',
      officerName: 'E2E Admin',
      officerEmail: ADMIN_EMAIL,
      officerPassword: ADMIN_PASSWORD,
    }),
  });
  if (res.status !== 201) throw new Error(`e2e bootstrap failed: ${res.status} ${await res.text()}`);
  process.env['E2E_INSTITUTION_ID'] = (await res.json()).institution.id;
}
