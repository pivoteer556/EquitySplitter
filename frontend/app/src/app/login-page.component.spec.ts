import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { LoginPageComponent } from './login-page.component';
import { expectPasswordRule } from './password-rule.testing';

describe('LoginPageComponent', () => {
  // `err` is the institution outcome (undefined = success); `userErr` (null = success, default 401: no such user account) is the owner/buyer/admin outcome.
  // `calls` records institution attempts, `userCalls` records user attempts.
  function setup(err: unknown, calls: string[][] = [], userErr: unknown = { status: 401 }, userCalls: string[][] = [], registerCalls: unknown[] = [], registerErr: unknown = null) {
    const api = {
      ownerLogin: (email: string, password: string) => {
        userCalls.push([email, password]);
        return userErr === null ? of({}) : throwError(() => userErr);
      },
      institutionLogin: (email: string, password: string) => {
        calls.push([email, password]);
        return err === undefined ? of({}) : throwError(() => err);
      },
      ownerRegister: (payload: unknown) => {
        registerCalls.push(payload);
        return registerErr === null ? of({}) : throwError(() => registerErr);
      },
    };
    TestBed.configureTestingModule({
      imports: [LoginPageComponent],
      providers: [
        { provide: ApiService, useValue: api },
        provideRouter([]),
      ],
    });
    const fixture = TestBed.createComponent(LoginPageComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('styles buttons and headings from the brand palette (global styles.css)', () => {
    const root = setup(undefined).nativeElement as HTMLElement;
    const button = getComputedStyle(root.querySelector('button[type=submit]')!);
    expect(button.backgroundColor).toBe('rgb(58, 95, 176)'); // --brand-blue #3A5FB0
    expect(button.color).toBe('rgb(255, 255, 255)');
    expect(getComputedStyle(root.querySelector('h1')!).color).toBe('rgb(20, 33, 61)'); // --brand-navy #14213D
  });

  it('draws the card as a cream surface with an amber border, distinct from the night page', () => {
    const root = setup(undefined).nativeElement as HTMLElement;
    const card = getComputedStyle(root.querySelector('.login-shell')!);
    expect(card.backgroundColor).toBe('rgb(248, 237, 203)'); // --brand-surface #F8EDCB
    expect(card.borderTopColor).toBe('rgb(217, 185, 106)'); // --brand-border #D9B96A
    expect(card.backgroundColor).not.toBe(getComputedStyle(document.body).backgroundColor);
  });

  it('shows a plain sentence when login fails with 401', () => {
    const fixture = setup({ status: 401, error: { detail: 'Invalid credentials' } });
    fixture.componentInstance.login();
    fixture.detectChanges();
    const el = (fixture.nativeElement as HTMLElement).querySelector('.error');
    expect(el?.textContent?.trim()).toBe('Incorrect email or password.');
  });

  // Convention for the UI series: native <form> + <label> + HTML validation attributes; no TS validation.
  describe('sign-in form', () => {
    async function form(calls: string[][] = []) {
      const fixture = setup(undefined, calls);
      const root = fixture.nativeElement as HTMLElement;
      await fixture.whenStable(); // ngModel registers its controls in a microtask
      const f = root.querySelector('#signin-form') as HTMLFormElement;
      const fill = (name: string, value: string) => {
        const i = f.querySelector(`input[name="${name}"]`) as HTMLInputElement;
        i.value = value;
        i.dispatchEvent(new Event('input'));
      };
      return { fixture, root, f, fill };
    }

    it('has labelled, typed, autocompleting, required inputs', async () => {
      const { f } = await form();
      const email = f.querySelector('input[name="email"]') as HTMLInputElement;
      const pw = f.querySelector('input[name="password"]') as HTMLInputElement;
      expect(email.type).toBe('email');
      expect(email.autocomplete).toBe('username');
      expect(email.required).toBeTrue();
      expect(pw.type).toBe('password');
      expect(pw.autocomplete).toBe('current-password');
      expect(pw.required).toBeTrue();
      expect(email.labels?.length).toBe(1);
      expect(pw.labels?.length).toBe(1);
      expect((f.querySelector('button[type="submit"]') as HTMLButtonElement)).toBeTruthy();
    });

    it('blocks submit natively when email is empty', async () => {
      const calls: string[][] = [];
      const { f, fill } = await form(calls);
      fill('password', 'pw');
      f.requestSubmit();
      expect(f.checkValidity()).toBeFalse();
      expect(calls.length).toBe(0);
    });

    it('blocks submit natively when email is malformed', async () => {
      const calls: string[][] = [];
      const { f, fill } = await form(calls);
      fill('email', 'not-an-email');
      fill('password', 'pw');
      f.requestSubmit();
      expect(calls.length).toBe(0);
    });

    it('submits with the entered credentials when valid', async () => {
      const calls: string[][] = [];
      const { f, fill } = await form(calls);
      fill('email', 'a@b.com');
      fill('password', 'secret');
      f.requestSubmit();
      expect(calls).toEqual([['a@b.com', 'secret']]);
    });

    it('marks the error area as an alert', async () => {
      const { fixture, root } = await form();
      fixture.componentInstance.error = 'boom';
      fixture.detectChanges();
      expect(root.querySelector('.error')?.getAttribute('role')).toBe('alert');
    });
  });

  it('does not show the bootstrap form and does not link to /bootstrap', () => {
    const root = setup(undefined).nativeElement as HTMLElement;
    expect(root.querySelector('#bootstrap-form')).toBeNull();
    expect(root.querySelector('#setup-note')).toBeNull();
    expect(root.querySelector('input[name="setupToken"]')).toBeNull();
    expect(root.textContent).not.toContain('Bootstrap');
    expect(root.querySelector('a[href="/bootstrap"]')).toBeNull();
  });

  // One form signs in every kind of account: owner/buyer/admin (user login) or officer (institution login).
  describe('unified sign-in routing', () => {
    function go(instErr: unknown, userErr: unknown) {
      const calls: string[][] = [];
      const userCalls: string[][] = [];
      const fixture = setup(instErr, calls, userErr, userCalls);
      const nav = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
      const c = fixture.componentInstance;
      c.loginEmail = 'a@b.com';
      c.loginPassword = 'pw';
      c.login();
      fixture.detectChanges();
      return { fixture, nav, calls, userCalls };
    }

    it('signs an owner in via the user login and goes to /listings without trying the institution', () => {
      const { nav, calls, userCalls } = go({ status: 401 }, null);
      expect(userCalls).toEqual([['a@b.com', 'pw']]);
      expect(calls).toEqual([]);
      expect(nav).toHaveBeenCalledWith('/listings');
    });

    it('falls back to the institution login on a user 401 and goes to /workbench', () => {
      const { nav, calls } = go(undefined, { status: 401 });
      expect(calls).toEqual([['a@b.com', 'pw']]);
      expect(nav).toHaveBeenCalledWith('/workbench');
    });

    it('shows one plain message when both logins return 401', () => {
      const { fixture, nav } = go({ status: 401 }, { status: 401 });
      expect((fixture.nativeElement as HTMLElement).querySelector('.error')?.textContent?.trim()).toBe('Incorrect email or password.');
      expect(nav).not.toHaveBeenCalled();
    });

    it('still tries the institution when the user login is rate limited (separate buckets), and reports the 429 if that fails', () => {
      const { fixture, nav, calls } = go({ status: 401 }, { status: 429, headers: { get: () => '30' } });
      expect(calls.length).toBe(1);
      expect(nav).not.toHaveBeenCalled();
      expect((fixture.nativeElement as HTMLElement).querySelector('.error')?.textContent).not.toContain('Incorrect email or password.');
    });

    it('does not try the institution after a server or network error on the user login', () => {
      const { fixture, calls } = go({ status: 401 }, { status: 500 });
      expect(calls).toEqual([]);
      expect((fixture.nativeElement as HTMLElement).querySelector('.error')).toBeTruthy();
    });
  });

  describe('create account (owner sign-up, same as the old /buyer form)', () => {
    it('submits name, email and password to ownerRegister and goes to /listings', async () => {
      const registerCalls: unknown[] = [];
      const fixture = setup(undefined, [], { status: 401 }, [], registerCalls);
      const nav = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
      const root = fixture.nativeElement as HTMLElement;
      const f = root.querySelector('form[aria-label="Create account"]') as HTMLFormElement;
      expect(f).toBeTruthy();
      const set = (id: string, v: string) => ((f.querySelector(id) as HTMLInputElement).value = v);
      set('input[name="name"]', 'Ann');
      set('input[name="email"]', 'ann@b.com');
      set('input[name="password"]', 'Str0ng!Passw0rd');
      f.requestSubmit();
      expect(registerCalls).toEqual([{ name: 'Ann', email: 'ann@b.com', password: 'Str0ng!Passw0rd' }]);
      expect(nav).toHaveBeenCalledWith('/listings');
    });

    // Ported from the removed buyer-page spec.
    function createForm(registerErr: unknown = null, registerCalls: unknown[] = []) {
      const fixture = setup(undefined, [], { status: 401 }, [], registerCalls, registerErr);
      spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
      const f = (fixture.nativeElement as HTMLElement).querySelector('form[aria-label="Create account"]') as HTMLFormElement;
      const fill = (name: string, v: string) => ((f.querySelector(`input[name="${name}"]`) as HTMLInputElement).value = v);
      return { fixture, f, fill };
    }

    it('advertises the password rule on the create-account password field', () => {
      expectPasswordRule(createForm().f.querySelector('input[name="password"]') as HTMLInputElement);
    });

    it('blocks create-account natively for a non-compliant password', () => {
      const registerCalls: unknown[] = [];
      const { f, fill } = createForm(null, registerCalls);
      fill('name', 'Ann');
      fill('email', 'ann@b.com');
      fill('password', 'alllowercase1234!');
      f.requestSubmit();
      fill('password', 'Sh0rt!');
      f.requestSubmit();
      expect(registerCalls.length).toBe(0);
    });

    it('shows a 409 in the create-account alert only, not the sign-in alert', () => {
      const { fixture, f, fill } = createForm({ status: 409, error: { detail: 'Email already registered' } });
      fill('name', 'Ann');
      fill('email', 'ann@b.com');
      fill('password', 'Str0ng!Passw0rd');
      f.requestSubmit();
      fixture.detectChanges();
      expect(f.querySelector('[role="alert"]')?.textContent?.trim()).toBe('Email already registered');
      expect((fixture.nativeElement as HTMLElement).querySelector('#signin-form [role="alert"]')).toBeNull();
      expect((fixture.nativeElement as HTMLElement).querySelector('pre.error')).toBeNull();
    });
  });
});
