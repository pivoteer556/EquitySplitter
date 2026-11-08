import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { environment } from '../environments/environment';
import { ApiService } from './api.service';
import { ListingsPageComponent } from './listings-page.component';
import { Listing } from './models';

const URL = `${environment.apiBaseUrl}/listings`;

describe('ApiService.getListings', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  function setup() {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    return { api: TestBed.inject(ApiService), http: TestBed.inject(HttpTestingController) };
  }

  it('GETs /listings with limit and offset', () => {
    const { api, http } = setup();
    api.getListings(20, 40).subscribe();
    const req = http.expectOne((r) => r.url === URL);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('limit')).toBe('20');
    expect(req.request.params.get('offset')).toBe('40');
    req.flush([]);
    http.verify();
  });

  it('sends the user token when only a buyer is signed in', () => {
    const { api, http } = setup();
    api.setUserToken('buyer-jwt');
    api.getListings(20, 0).subscribe();
    const req = http.expectOne((r) => r.url === URL);
    expect(req.request.headers.get('Authorization')).toBe('Bearer buyer-jwt');
    req.flush([]);
  });

  it('sends the institution token when only an officer is signed in', () => {
    const { api, http } = setup();
    api.setInstitutionToken('officer-jwt');
    api.getListings(20, 0).subscribe();
    const req = http.expectOne((r) => r.url === URL);
    expect(req.request.headers.get('Authorization')).toBe('Bearer officer-jwt');
    req.flush([]);
  });
});

describe('ListingsPageComponent', () => {
  const item = (n: number): Listing => ({
    id: `id-${n}`,
    address: `${n} Main St`,
    status: 'pending_acknowledgement',
    createdAt: '2026-03-05T10:00:00Z',
  });
  const many = (from: number, count: number) => Array.from({ length: count }, (_, i) => item(from + i));

  async function setup() {
    TestBed.configureTestingModule({
      imports: [ListingsPageComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(ListingsPageComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const settle = async () => {
      await fixture.whenStable();
      fixture.detectChanges();
    };
    const flush = async (body: object | null, status = 200) => {
      const req = http.expectOne((r) => r.url === URL);
      if (status === 200) req.flush(body);
      else req.flush(body, { status, statusText: 'err' });
      await settle();
      return req;
    };
    return { fixture, root, http, flush, settle };
  }

  it('shows loading text until the request returns', async () => {
    const { root, flush } = await setup();
    expect(root.textContent).toContain('Loading');
    await flush([]);
    expect(root.textContent).not.toContain('Loading');
  });

  it('renders each listing with address, a <time datetime> and plain status', async () => {
    const { root, flush } = await setup();
    const req = await flush([item(1), item(2)]);
    expect(req.request.params.get('limit')).toBe('20');
    expect(req.request.params.get('offset')).toBe('0');
    const rows = root.querySelectorAll('ul > li');
    expect(rows.length).toBe(2);
    expect(rows[0].querySelector('h2')?.textContent?.trim()).toBe('1 Main St');
    const time = rows[0].querySelector('time') as HTMLTimeElement;
    expect(time.getAttribute('datetime')).toBe('2026-03-05T10:00:00Z');
    expect(time.textContent?.trim()).toBe('Mar 5, 2026');
    expect(rows[0].textContent).toContain('Awaiting owner sign-off');
    expect(rows[0].textContent).not.toContain('pending_acknowledgement');
    expect(root.querySelector('button')).toBeNull();
  });

  it('shows the empty state', async () => {
    const { root, flush } = await setup();
    await flush([]);
    expect(root.textContent).toContain('No properties are listed right now.');
  });

  it('shows a friendly error with role=alert', async () => {
    const { root, flush } = await setup();
    await flush({}, 500);
    const alert = root.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('Something went wrong. Please try again.');
  });

  it('on 401 shows a sign-in message with a link to /login', async () => {
    const { root, flush } = await setup();
    await flush({ detail: 'Not authenticated' }, 401);
    const alert = root.querySelector('[role="alert"]') as HTMLElement;
    expect(alert.textContent).toContain('sign in');
    expect(alert.querySelector('a')?.getAttribute('href')).toBe('/login');
  });

  it('Load more appends the next page and hides after a short page', async () => {
    const { root, http, settle, flush } = await setup();
    await flush(many(1, 20));
    expect(root.querySelectorAll('ul > li').length).toBe(20);
    const button = root.querySelector('button') as HTMLButtonElement;
    expect(button.textContent).toContain('Load more');
    button.click();
    const req = http.expectOne((r) => r.url === URL);
    expect(req.request.params.get('offset')).toBe('20');
    req.flush(many(21, 3));
    await settle();
    expect(root.querySelectorAll('ul > li').length).toBe(23);
    expect(root.querySelector('button')).toBeNull();
  });
});
