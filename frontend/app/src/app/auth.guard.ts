import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';

export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  const token = localStorage.getItem('institutionToken');
  if (token && token.trim().length > 0) {
    return true;
  }
  return router.createUrlTree(['/login']);
};
