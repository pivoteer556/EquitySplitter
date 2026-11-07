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

  it('defaults to the local API', () => {
    expect(environment.apiBaseUrl).toBe('http://127.0.0.1:8000/api/v1');
  });

  it('production points at the hosted API, not localhost', () => {
    expect(productionEnvironment.apiBaseUrl).toMatch(/^https:\/\/.+\.azurecontainerapps\.io\/api\/v1$/);
    expect(productionEnvironment.apiBaseUrl).not.toContain('127.0.0.1');
  });
});
