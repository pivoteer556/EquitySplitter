import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, Subject, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { BuyerPageComponent } from './buyer-page.component';

const GOOD = 'Str0ng!Passw0rd';

describe('BuyerPageComponent', () => {
  async function setup(opts: { loginErr?: unknown; registerErr?: unknown; pending?: boolean } = {}) {
    const loginCalls: string[][] = [];
    const registerCalls: unknown[] = [];
    const pending = new Subject<unknown>();
    const api = {
      ownerLogin: (email: string, password: string) => {
        loginCalls.push([email, password]);
        if (opts.pending) return pending;
        return opts.loginErr === undefined ? of({ accessToken: 'x' }) : throwError(() => opts.loginErr);
      },
      ownerRegister: (payload: unknown) => {
        registerCalls.push(payload);
        return opts.registerErr === undefined ? of({ accessToken: 'x' }) : throwError(() => opts.registerErr);
      },
    };
    TestBed.configureTestingModule({
      providers: [
        { provide: ApiService, useValue: api },
        provideRouter([
          { path: 'buyer', component: BuyerPageComponent },
          { path: 'listings', children: [] },
          { path: 'login', children: [] },
        ]),
      ],
    });
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/buyer', BuyerPageComponent);
    harness.detectChanges();
    const root = harness.routeNativeElement as HTMLElement;
    const signIn = root.querySelector('form[aria-label="Sign in"]') as HTMLFormElement;
    const create = root.querySelector('form[aria-label="Create account"]') as HTMLFormElement;
    const fill = (f: HTMLFormElement, name: string, value: string) => {
      const i = f.querySelector(`input[name="${name}"]`) as HTMLInputElement;
      i.value = value;
      i.dispatchEvent(new Event('input'));
    };
    const alertOf = (f: HTMLFormElement) => f.querySelector('[role="alert"]')?.textContent?.trim() ?? '';
    return { harness, root, signIn, create, fill, alertOf, loginCalls, registerCalls };
  }

  it('links to the institution sign-in page', async () => {
    const { root } = await setup();
    const a = root.querySelector('a[href="/login"]');
    expect(a?.textContent).toContain('Institution sign-in');
  });

  it('blocks sign-in natively for empty and malformed email', async () => {
    const { signIn, fill, loginCalls } = await setup();
    signIn.requestSubmit();
    fill(signIn, 'email', 'not-an-email');
    fill(signIn, 'password', 'x');
    signIn.requestSubmit();
    expect(loginCalls.length).toBe(0);
  });

  it('signs in once and navigates to /listings', async () => {
    const { harness, signIn, fill, loginCalls } = await setup();
    fill(signIn, 'email', 'b@example.com');
    fill(signIn, 'password', 'pw');
    signIn.requestSubmit();
    await harness.fixture.whenStable();
    expect(loginCalls).toEqual([['b@example.com', 'pw']]);
    expect(TestBed.inject(Router).url).toBe('/listings');
  });

  it('blocks create-account natively for a non-compliant password', async () => {
    const { create, fill, registerCalls } = await setup();
    fill(create, 'name', 'Bo Buyer');
    fill(create, 'email', 'b@example.com');
    fill(create, 'password', 'alllowercase1234!');
    create.requestSubmit();
    fill(create, 'password', 'Sh0rt!');
    create.requestSubmit();
    expect(registerCalls.length).toBe(0);
  });

  it('registers once and navigates to /listings', async () => {
    const { harness, create, fill, registerCalls } = await setup();
    fill(create, 'name', 'Bo Buyer');
    fill(create, 'email', 'b@example.com');
    fill(create, 'password', GOOD);
    create.requestSubmit();
    await harness.fixture.whenStable();
    expect(registerCalls).toEqual([{ name: 'Bo Buyer', email: 'b@example.com', password: GOOD }]);
    expect(TestBed.inject(Router).url).toBe('/listings');
  });

  it('shows a 401 in the sign-in alert only', async () => {
    const { harness, signIn, create, fill, alertOf } = await setup({ loginErr: { status: 401, error: { detail: 'Invalid credentials' } } });
    fill(signIn, 'email', 'b@example.com');
    fill(signIn, 'password', 'pw');
    signIn.requestSubmit();
    harness.detectChanges();
    expect(alertOf(signIn)).toBe('Incorrect email or password.');
    expect(alertOf(create)).toBe('');
  });

  it('shows a 409 in the register alert only', async () => {
    const { harness, signIn, create, fill, alertOf } = await setup({ registerErr: { status: 409, error: { detail: 'Email already registered' } } });
    fill(create, 'name', 'Bo Buyer');
    fill(create, 'email', 'b@example.com');
    fill(create, 'password', GOOD);
    create.requestSubmit();
    harness.detectChanges();
    expect(alertOf(create)).toBe('Email already registered');
    expect(alertOf(signIn)).toBe('');
  });

  it('keeps the two loading states independent', async () => {
    const { harness, signIn, create, fill } = await setup({ pending: true });
    fill(signIn, 'email', 'b@example.com');
    fill(signIn, 'password', 'pw');
    signIn.requestSubmit();
    harness.detectChanges();
    expect((signIn.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeTrue();
    expect((create.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeFalse();
  });
});
