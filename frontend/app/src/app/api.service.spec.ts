import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../environments/environment';
import { environment as productionEnvironment } from '../environments/environment.production';
import { ApiService } from './api.service';

describe('ApiService base URL', () => {
  it('posts institution login under the configured apiBaseUrl', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(ApiService);
    const http = TestBed.inject(HttpTestingController);

    api.institutionLogin('a@b.c', 'x').subscribe();

    http.expectOne(`${environment.apiBaseUrl}/auth/institution/login`).flush({ accessToken: 'not-a-jwt' });
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
