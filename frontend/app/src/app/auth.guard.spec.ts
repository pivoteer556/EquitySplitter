import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, provideRouter, RouterStateSnapshot, UrlTree } from '@angular/router';

import { authGuard, officerGuard } from './auth.guard';
import { routes } from './app.routes';

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

describe('officerGuard', () => {
  function run() {
    return TestBed.runInInjectionContext(() =>
      officerGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
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

  it('rejects a user token alone', () => {
    localStorage.setItem('userToken', 'user');
    expect((run() as UrlTree).toString()).toBe('/login');
  });

  it('rejects no token', () => {
    expect((run() as UrlTree).toString()).toBe('/login');
  });
});

describe('route guards', () => {
  it('protects /workbench with officerGuard and /listings with authGuard; /buyer is open', () => {
    const by = (p: string) => routes.find((r) => r.path === p)!;
    expect(by('workbench').canActivate).toEqual([officerGuard]);
    expect(by('listings').canActivate).toEqual([authGuard]);
    expect(by('buyer').canActivate).toBeUndefined();
  });
});
