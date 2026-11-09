import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { LoginPageComponent } from './login-page.component';
import { expectPasswordRule } from './password-rule.testing';

describe('LoginPageComponent', () => {
  // `err` is the login outcome (undefined = success returning `result`); `calls` records login attempts.
  const USER = { userType: 'user', isPlatformAdmin: false, role: null, institutionId: null };
  function setup(err: unknown, calls: string[][] = [], result: unknown = USER, registerCalls: unknown[] = [], registerErr: unknown = null) {
    const api = {
      login: (email: string, password: string) => {
        calls.push([email, password]);
        return err === undefined ? of(result) : throwError(() => err);
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

  // One form, one request: the server says what kind of account signed in.
  describe('unified sign-in routing', () => {
    function go(err: unknown, result: unknown = USER) {
      const calls: string[][] = [];
      const fixture = setup(err, calls, result);
      const nav = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
      const c = fixture.componentInstance;
      c.loginEmail = 'a@b.com';
      c.loginPassword = 'pw';
      c.login();
      fixture.detectChanges();
      return { fixture, nav, calls };
    }

    it('sends an owner to /listings with a single login call', () => {
      const { nav, calls } = go(undefined);
      expect(calls).toEqual([['a@b.com', 'pw']]);
      expect(nav).toHaveBeenCalledWith('/listings');
    });

    it('sends an officer (institution_user) to /workbench', () => {
      const { nav } = go(undefined, { userType: 'institution_user', isPlatformAdmin: false, role: 'admin', institutionId: 'i1' });
      expect(nav).toHaveBeenCalledWith('/workbench');
    });

    it('sends a platform admin to /bootstrap', () => {
      const { nav } = go(undefined, { userType: 'user', isPlatformAdmin: true, role: null, institutionId: null });
      expect(nav).toHaveBeenCalledWith('/bootstrap');
    });

    it('shows one plain message on 401 and makes only one call', () => {
      const { fixture, nav, calls } = go({ status: 401 });
      expect(calls.length).toBe(1);
      expect((fixture.nativeElement as HTMLElement).querySelector('.error')?.textContent?.trim()).toBe('Incorrect email or password.');
      expect(nav).not.toHaveBeenCalled();
    });

    it('reports a 429 as the rate-limit message, not as a wrong password', () => {
      const { fixture, nav } = go({ status: 429, headers: { get: () => '30' } });
      const text = (fixture.nativeElement as HTMLElement).querySelector('.error')?.textContent ?? '';
      expect(text).toBeTruthy();
      expect(text).not.toContain('Incorrect email or password.');
      expect(nav).not.toHaveBeenCalled();
    });

    it('shows an error after a server error', () => {
      const { fixture } = go({ status: 500 });
      expect((fixture.nativeElement as HTMLElement).querySelector('.error')).toBeTruthy();
    });

    it('sends the submitted credentials even if the fields are edited while the request is pending', () => {
      const calls: string[][] = [];
      const pending = new Subject<unknown>();
      const fixture = setup(undefined, calls);
      (TestBed.inject(ApiService) as unknown as { login: unknown }).login = (e: string, p: string) => {
        calls.push([e, p]);
        return pending;
      };
      const nav = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
      const c = fixture.componentInstance;
      c.loginEmail = 'a@b.com';
      c.loginPassword = 'pw';
      c.login();
      c.loginEmail = 'edited@b.com';
      c.loginPassword = 'edited';
      pending.next({ ...USER, userType: 'institution_user' });
      expect(calls).toEqual([['a@b.com', 'pw']]);
      expect(nav).toHaveBeenCalledWith('/workbench');
    });
  });

  describe('second factor', () => {
    const CHALLENGE = { userType: 'institution_user', secondFactorRequired: true, challengeToken: 'chal' };
    const OFFICER = { userType: 'institution_user', isPlatformAdmin: false, role: 'admin', institutionId: 'i1' };
    function twoStep(totpErr?: unknown) {
      const totpCalls: string[][] = [];
      const api = {
        login: () => of(CHALLENGE),
        loginTotp: (t: string, c: string) => {
          totpCalls.push([t, c]);
          return totpErr === undefined ? of(OFFICER) : throwError(() => totpErr);
        },
      };
      TestBed.configureTestingModule({ imports: [LoginPageComponent], providers: [{ provide: ApiService, useValue: api }, provideRouter([])] });
      const fixture = TestBed.createComponent(LoginPageComponent);
      fixture.detectChanges();
      const nav = spyOn(TestBed.inject(Router), 'navigateByUrl').and.resolveTo(true);
      const c = fixture.componentInstance;
      c.loginEmail = 'o@b.com';
      c.loginPassword = 'pw';
      c.login();
      fixture.detectChanges();
      return { fixture, nav, totpCalls, c };
    }
    const codeInput = (f: { nativeElement: unknown }) => (f.nativeElement as HTMLElement).querySelector<HTMLInputElement>('#login-code');

    it('shows no code field before a challenge', () => {
      const fixture = setup(undefined);
      expect(codeInput(fixture)).toBeNull();
    });

    it('a password-only result shows a 6-digit one-time-code field and does not navigate', () => {
      const { fixture, nav } = twoStep();
      const input = codeInput(fixture)!;
      expect(input).toBeTruthy();
      expect(input.getAttribute('inputmode')).toBe('numeric');
      expect(input.getAttribute('autocomplete')).toBe('one-time-code');
      expect(input.getAttribute('pattern')).toBe('[0-9]{6}');
      expect(input.required).toBeTrue();
      expect(nav).not.toHaveBeenCalled();
    });

    it('submitting the code sends the challenge and goes to /workbench', () => {
      const { c, nav, totpCalls, fixture } = twoStep();
      c.loginCode = '123456';
      c.submitCode();
      fixture.detectChanges();
      expect(totpCalls).toEqual([['chal', '123456']]);
      expect(nav).toHaveBeenCalledWith('/workbench');
    });

    it('a wrong code shows a code-specific message and does not navigate', () => {
      const { c, nav, fixture } = twoStep({ status: 401 });
      c.loginCode = '000000';
      c.submitCode();
      fixture.detectChanges();
      expect((fixture.nativeElement as HTMLElement).querySelector('.error')?.textContent?.trim()).toBe('Incorrect or expired code. Check your authenticator app and try again.');
      expect(nav).not.toHaveBeenCalled();
    });
  });

  describe('create account (owner sign-up, same as the old /buyer form)', () => {
    it('submits name, email and password to ownerRegister and goes to /listings', async () => {
      const registerCalls: unknown[] = [];
      const fixture = setup(undefined, [], USER, registerCalls);
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
      const fixture = setup(undefined, [], USER, registerCalls, registerErr);
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
