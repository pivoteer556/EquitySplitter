import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { LoginPageComponent } from './login-page.component';

describe('LoginPageComponent', () => {
  function setup(err: unknown, calls: string[][] = [], bootstrapCalls: Record<string, string>[] = []) {
    const api = {
      institutionLogin: (email: string, password: string) => {
        calls.push([email, password]);
        return err === undefined ? of({}) : throwError(() => err);
      },
      bootstrapInstitution: (payload: Record<string, string>) => {
        bootstrapCalls.push(payload);
        return err === undefined
          ? of({ institution: { id: 'i' }, institutionUser: {}, activationToken: 'tok', activationPath: '/activate#token=tok' })
          : throwError(() => err);
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

  it('starts the bootstrap form empty and explains the setup token', () => {
    const fixture = setup(undefined);
    const c = fixture.componentInstance;
    expect([c.institutionName, c.officerName, c.officerEmail]).toEqual(['', '', '']);
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('#setup-note')?.textContent).toContain('requires a setup token');
    for (const n of ['institutionName', 'officerName', 'officerEmail']) {
      expect(root.querySelector(`#bootstrap-form input[name="${n}"]`)?.hasAttribute('required')).toBeTrue();
    }
  });

  it('shows a plain sentence when login fails with 401', () => {
    const fixture = setup({ status: 401, error: { detail: 'Invalid credentials' } });
    fixture.componentInstance.login();
    fixture.detectChanges();
    const el = (fixture.nativeElement as HTMLElement).querySelector('.error');
    expect(el?.textContent?.trim()).toBe('Incorrect email or password.');
  });

  it('shows a plain sentence when bootstrap fails with no connection', () => {
    const fixture = setup({ status: 0, error: new ProgressEvent('error') });
    fixture.componentInstance.bootstrapInstitution();
    fixture.detectChanges();
    const el = (fixture.nativeElement as HTMLElement).querySelector('.error');
    expect(el?.textContent?.trim()).toBe(
      "Can't reach the server. Check your connection and try again.",
    );
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

  describe('bootstrap form', () => {
    async function bform(err: unknown = undefined, bootstrapCalls: Record<string, string>[] = []) {
      const fixture = setup(err, [], bootstrapCalls);
      await fixture.whenStable(); // ngModel registers its controls in a microtask
      const f = (fixture.nativeElement as HTMLElement).querySelector('#bootstrap-form') as HTMLFormElement;
      const token = f.querySelector('input[name="setupToken"]') as HTMLInputElement;
      const type = (v: string) => {
        token.value = v;
        token.dispatchEvent(new Event('input'));
        fixture.detectChanges(); // like a real keystroke: change detection sees the typed value before it is cleared
      };
      return { fixture, f, token, type };
    }

    it('has a labelled, required, non-autocompleting password-type setup token input and no officer password', async () => {
      const { f, token } = await bform();
      expect(token.type).toBe('password');
      expect(token.required).toBe(true);
      expect(token.getAttribute('autocomplete')).toBe('off');
      expect(f.querySelector(`label[for="${token.id}"]`)?.textContent?.trim()).toBe('Setup token');
      expect(f.querySelectorAll('input[type="password"]').length).toBe(1);
    });

    it('sends the setup token separately from the payload, shows the full activation link, clears the token and does not navigate', async () => {
      const bootstrapCalls: Record<string, string>[] = [];
      const { fixture, type, token } = await bform(undefined, bootstrapCalls);
      const router = TestBed.inject(Router);
      const nav = spyOn(router, 'navigateByUrl');
      type('s3cret');
      fixture.componentInstance.bootstrapInstitution();
      fixture.detectChanges();
      await fixture.whenStable();
      await new Promise((r) => setTimeout(r)); // ngModel writes the cleared value to the DOM in a later microtask
      expect(Object.keys(bootstrapCalls[0]).sort()).toEqual(['institutionName', 'officerEmail', 'officerName']);
      expect((bootstrapCalls[0] as unknown as { setupToken: string }).setupToken).toBeUndefined();
      expect(bootstrapCalls.length).toBe(1);
      const link = (fixture.nativeElement as HTMLElement).querySelector('.activation a') as HTMLAnchorElement;
      expect(link.textContent?.trim()).toBe(`${window.location.origin}/activate#token=tok`);
      expect(nav).not.toHaveBeenCalled();
      expect(fixture.componentInstance.setupToken).toBe('');
      expect(token.value).toBe('');
    });

    it('passes the typed token to the api as the second argument', async () => {
      const fixture = setup(undefined);
      const api = TestBed.inject(ApiService) as unknown as { bootstrapInstitution: (p: unknown, t: string) => unknown };
      const spy = spyOn(api, 'bootstrapInstitution').and.callThrough();
      fixture.componentInstance.setupToken = 'abc';
      fixture.componentInstance.bootstrapInstitution();
      expect(spy.calls.mostRecent().args[1]).toBe('abc');
    });

    it('shows a clear generic message on 404, no activation link, and clears the token', async () => {
      const { fixture, type, token } = await bform({ status: 404, error: { detail: 'Not found' } });
      type('wrong');
      fixture.componentInstance.bootstrapInstitution();
      fixture.detectChanges();
      await fixture.whenStable();
      await new Promise((r) => setTimeout(r)); // ngModel writes the cleared value to the DOM in a later microtask
      const root = fixture.nativeElement as HTMLElement;
      expect(root.querySelector('.error')?.textContent?.trim()).toBe('Setup token not accepted.');
      expect(root.querySelector('.activation')).toBeNull();
      expect(fixture.componentInstance.setupToken).toBe('');
      expect(token.value).toBe('');
    });

    it('does not store the token in localStorage or sessionStorage', async () => {
      const { fixture, type } = await bform();
      type('s3cret');
      fixture.componentInstance.bootstrapInstitution();
      const dump = JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage });
      expect(dump).not.toContain('s3cret');
    });
  });

  it('links to the buyer page', () => {
    const fixture = setup(undefined);
    expect(fixture.nativeElement.querySelector('a[href="/buyer"]')?.textContent).toContain('Sign in as a buyer');
  });
});
