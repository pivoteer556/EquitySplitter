import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';

export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  // A signed-in officer (institution token) or owner/buyer (user token) may pass.
  const hasToken = ['institutionToken', 'userToken'].some((k) => (localStorage.getItem(k) ?? '').trim().length > 0);
  if (hasToken) {
    return true;
  }
  return router.createUrlTree(['/login']);
};

/** Officer-only pages: admits an institution token, not a buyer's user token. */
export const officerGuard: CanActivateFn = () => {
  const router = inject(Router);
  const ok = (localStorage.getItem('institutionToken') ?? '').trim().length > 0;
  return ok ? true : router.createUrlTree(['/login']);
};
