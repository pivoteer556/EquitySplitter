import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { LoginPageComponent } from './login-page.component';

describe('LoginPageComponent', () => {
  function setup(err: unknown, calls: string[][] = []) {
    const api = {
      institutionLogin: (email: string, password: string) => {
        calls.push([email, password]);
        return err === undefined ? of({}) : throwError(() => err);
      },
      bootstrapInstitution: () => throwError(() => err),
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
      const f = root.querySelector('form') as HTMLFormElement;
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

  it('links to the buyer page', () => {
    const fixture = setup(undefined);
    expect(fixture.nativeElement.querySelector('a[href="/buyer"]')?.textContent).toContain('Sign in as a buyer');
  });
});
