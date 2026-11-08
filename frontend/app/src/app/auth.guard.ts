import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';

export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  // A signed-in officer (institution token) or buyer/owner (user token) may pass.
  const hasToken = ['institutionToken', 'userToken'].some((k) => (localStorage.getItem(k) ?? '').trim().length > 0);
  if (hasToken) {
    return true;
  }
  return router.createUrlTree(['/login']);
};
