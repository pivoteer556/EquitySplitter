const GENERIC = 'Something went wrong. Please try again.';

/** Turns an HttpErrorResponse-like value into one plain sentence for the user. */
export function friendlyError(err: unknown, unauthorized = 'Incorrect email or password.'): string {
  const e = (err ?? {}) as { status?: unknown; error?: { detail?: unknown } | null };
  if (e.status === 0) return "Can't reach the server. Check your connection and try again.";
  if (e.status === 401) return unauthorized;
  if (e.status === 429) return 'Too many attempts. Please wait a minute and try again.';
  const detail = e.error?.detail;
  return typeof detail === 'string' && detail.trim() ? detail : GENERIC;
}
