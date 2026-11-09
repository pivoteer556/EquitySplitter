import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../environments/environment';
import { environment as productionEnvironment } from '../environments/environment.production';
import { ApiService } from './api.service';

describe('ApiService base URL', () => {
  function loginSetup() {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);
    api.clearTokens();
    api.setInstitutionId('');
    return { api, http };
  }

  it('login posts once to /auth/login under the configured apiBaseUrl and stores a user token', () => {
    const { api, http } = loginSetup();
    let result: unknown;

    api.login('a@b.c', 'x').subscribe((r) => (result = r));

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/login`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'a@b.c', password: 'x' });
    req.flush({ accessToken: 'user-jwt', tokenType: 'Bearer', userType: 'user', isPlatformAdmin: true, role: null, institutionId: null });
    expect(api.getUserToken()).toBe('user-jwt');
    expect(api.getInstitutionToken()).toBe('');
    expect((result as { isPlatformAdmin: boolean }).isPlatformAdmin).toBeTrue();
    api.clearTokens();
    http.verify();
  });

  it('login stores an institution_user as the officer token and institution id, not the user token', () => {
    const { api, http } = loginSetup();

    api.login('o@b.c', 'x').subscribe();

    http.expectOne(`${environment.apiBaseUrl}/auth/login`).flush({
      accessToken: 'officer-jwt', tokenType: 'Bearer', userType: 'institution_user', isPlatformAdmin: false, role: 'admin', institutionId: 'inst-9',
    });
    expect(api.getInstitutionToken()).toBe('officer-jwt');
    expect(api.getInstitutionId()).toBe('inst-9');
    expect(api.getUserToken()).toBe('');
    api.clearTokens();
    api.setInstitutionId('');
    http.verify();
  });

  it('posts accept-invite with token and password and stores the user token', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);

    api.acceptInvite('tok', 'Str0ng!Passw0rd').subscribe();

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/accept-invite`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ token: 'tok', password: 'Str0ng!Passw0rd' });
    req.flush({ accessToken: 'user-jwt' });
    expect(api.getUserToken()).toBe('user-jwt');
    api.clearTokens();
    http.verify();
  });

  it('bootstrap sends no password and stores no session', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);
    api.clearTokens();

    api.bootstrapInstitution({ institutionName: 'I', officerName: 'O', officerEmail: 'o@e.com' }, 'setup-tok').subscribe();

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/institution/bootstrap`);
    expect(req.request.headers.get('X-Bootstrap-Token')).toBe('setup-tok');
    expect(req.request.body).toEqual({ institutionName: 'I', officerName: 'O', officerEmail: 'o@e.com' });
    req.flush({ institution: { id: 'i1' }, institutionUser: {}, activationToken: 't', activationPath: '/activate#token=t' });
    expect(api.getInstitutionToken()).toBe('');
    expect(api.getInstitutionId()).toBe('');
    http.verify();
  });

  it('bootstrap sends the signed-in user token as the bearer and stores the rotated token, never in the body', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);
    api.clearTokens();
    api.setUserToken('admin-jwt');

    api.bootstrapInstitution({ institutionName: 'I', officerName: 'O', officerEmail: 'o@e.com' }, 'setup-tok').subscribe();

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/institution/bootstrap`);
    expect(req.request.headers.get('Authorization')).toBe('Bearer admin-jwt');
    expect(req.request.headers.get('X-Bootstrap-Token')).toBe('setup-tok');
    expect(JSON.stringify(req.request.body)).not.toContain('admin-jwt');
    expect(JSON.stringify(req.request.body)).not.toContain('setup-tok');
    req.flush(
      { institution: { id: 'i1' }, institutionUser: {}, activationToken: 't', activationPath: '/activate#token=t' },
      { headers: { 'X-Refreshed-Token': 'admin-jwt-2' } },
    );
    expect(api.getUserToken()).toBe('admin-jwt-2');
    api.clearTokens();
    http.verify();
  });

  it('bootstrap with no session sends no Authorization header', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);
    api.clearTokens();

    api.bootstrapInstitution({ institutionName: 'I', officerName: 'O', officerEmail: 'o@e.com' }, 'setup-tok').subscribe({ error: () => undefined });

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/institution/bootstrap`);
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({}, { status: 404, statusText: 'Not Found' });
    http.verify();
  });

  it('activate posts token and password and stores the institution session', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);
    const payload = btoa(JSON.stringify({ institutionId: 'inst-1' }));

    api.activateInstitutionUser('tok', 'Str0ng!Passw0rd').subscribe();

    const req = http.expectOne(`${environment.apiBaseUrl}/auth/institution/activate`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ token: 'tok', password: 'Str0ng!Passw0rd' });
    req.flush({ accessToken: `h.${payload}.s` });
    expect(api.getInstitutionToken()).toBe(`h.${payload}.s`);
    expect(api.getInstitutionId()).toBe('inst-1');
    api.clearTokens();
    api.setInstitutionId('');
    http.verify();
  });

  it('defaults to the local API', () => {
    expect(environment.apiBaseUrl).toBe('http://127.0.0.1:8000/api/v1');
  });

  it('production points at the hosted API, not localhost', () => {
    expect(productionEnvironment.apiBaseUrl).toMatch(/^https:\/\/.+\.azurecontainerapps\.io\/api\/v1$/);
    expect(productionEnvironment.apiBaseUrl).not.toContain('127.0.0.1');
  });
});
