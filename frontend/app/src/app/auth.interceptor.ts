import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { ApiService } from './api.service';

// A 401 from these means the one-time link or the typed code was bad, not that a session expired: stay on the page and show the error.
const TOKEN_LINK_PATHS = ['/auth/institution/activate', '/auth/accept-invite', '/auth/institution/totp/recovery-codes'];

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const api = inject(ApiService);
  return next(req).pipe(
    catchError((err: unknown) => {
      if (err instanceof HttpErrorResponse && err.status === 401 && !TOKEN_LINK_PATHS.some((p) => req.url.endsWith(p))) {
        api.clearTokens();
        router.navigateByUrl('/login');
      }
      return throwError(() => err);
    }),
  );
};
