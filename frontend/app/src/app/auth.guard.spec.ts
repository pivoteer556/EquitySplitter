import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, provideRouter, RouterStateSnapshot, UrlTree } from '@angular/router';

import { authGuard } from './auth.guard';

describe('authGuard', () => {
  function run() {
    return TestBed.runInInjectionContext(() =>
      authGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
    );
  }
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });
  afterEach(() => localStorage.clear());

  it('admits an institution token', () => {
    localStorage.setItem('institutionToken', 'inst');
    expect(run()).toBeTrue();
  });

  it('admits a user (buyer) token', () => {
    localStorage.setItem('userToken', 'user');
    expect(run()).toBeTrue();
  });

  it('redirects to /login with neither token', () => {
    const result = run() as UrlTree;
    expect(result.toString()).toBe('/login');
  });
});
