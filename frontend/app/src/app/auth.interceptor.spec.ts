import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  function setup() {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting()],
    });
    const nav = spyOn(TestBed.inject(Router), 'navigateByUrl');
    return { nav, http: TestBed.inject(HttpClient), ctl: TestBed.inject(HttpTestingController) };
  }

  it('sends the user to /login on a 401 from a protected endpoint', () => {
    const { nav, http, ctl } = setup();
    http.get('/api/v1/properties').subscribe({ error: () => undefined });
    ctl.expectOne('/api/v1/properties').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(nav).toHaveBeenCalledWith('/login');
  });

  for (const path of ['/api/v1/auth/institution/activate', '/api/v1/auth/accept-invite', '/api/v1/auth/institution/totp/recovery-codes']) {
    it(`keeps the user on the page when ${path} answers 401 (a bad link or a wrong code is not a lost session)`, () => {
      const { nav, http, ctl } = setup();
      http.post(path, {}).subscribe({ error: () => undefined });
      ctl.expectOne(path).flush({}, { status: 401, statusText: 'Unauthorized' });
      expect(nav).not.toHaveBeenCalled();
    });
  }
});
