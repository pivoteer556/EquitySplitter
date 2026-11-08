import { Location } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, throwError } from 'rxjs';

import { ActivatePageComponent } from './activate-page.component';
import { ApiService } from './api.service';

const TOKEN = 'header.payload.signature';
const GOOD = 'Str0ng!Passw0rd';

describe('ActivatePageComponent', () => {
  async function setup(url: string, err?: unknown, calls: string[][] = []) {
    const api = {
      activateInstitutionUser: (token: string, password: string) => {
        calls.push([token, password]);
        return err === undefined ? of({ accessToken: 'x' }) : throwError(() => err);
      },
    };
    TestBed.configureTestingModule({
      providers: [
        { provide: ApiService, useValue: api },
        provideRouter([
          { path: 'activate', component: ActivatePageComponent },
          { path: 'workbench', children: [] },
        ]),
      ],
    });
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(url, ActivatePageComponent);
    harness.detectChanges();
    const root = harness.routeNativeElement as HTMLElement;
    const f = root.querySelector('form') as HTMLFormElement | null;
    const fill = (name: string, value: string) => {
      const i = f!.querySelector(`input[name="${name}"]`) as HTMLInputElement;
      i.value = value;
      i.dispatchEvent(new Event('input'));
    };
    return { harness, root, f, fill, calls };
  }

  it('removes the token from the address bar and history entry', async () => {
    const { root } = await setup(`/activate#token=${TOKEN}`);
    const location = TestBed.inject(Location);
    expect(location.path(true)).toBe('/activate');
    expect(TestBed.inject(Router).url).not.toContain(TOKEN);
    expect(window.location.href).not.toContain(TOKEN);
    expect(root.textContent).not.toContain(TOKEN);
    expect(root.querySelector('form')).toBeTruthy();
  });

  it('shows a message and no form when there is no token', async () => {
    const { root, f } = await setup('/activate');
    expect(f).toBeNull();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('activation link');
  });

  it('has labelled, typed, required password inputs', async () => {
    const { f } = await setup(`/activate#token=${TOKEN}`);
    const pw = f!.querySelector('input[name="password"]') as HTMLInputElement;
    const cf = f!.querySelector('input[name="confirm"]') as HTMLInputElement;
    for (const i of [pw, cf]) {
      expect(i.type).toBe('password');
      expect(i.autocomplete).toBe('new-password');
      expect(i.required).toBeTrue();
      expect(i.labels?.length).toBe(1);
    }
    expect(pw.minLength).toBe(10);
  });

  it('blocks submit natively for empty, short, non-compliant and mismatched passwords', async () => {
    const calls: string[][] = [];
    const { f, fill } = await setup(`/activate#token=${TOKEN}`, undefined, calls);
    f!.requestSubmit();
    expect(calls.length).toBe(0);
    fill('password', 'Sh0rt!');
    fill('confirm', 'Sh0rt!');
    f!.requestSubmit();
    expect(calls.length).toBe(0);
    fill('password', 'alllowercase1234!');
    fill('confirm', 'alllowercase1234!');
    f!.requestSubmit();
    expect(calls.length).toBe(0);
    fill('password', GOOD);
    fill('confirm', GOOD + 'x');
    expect(f!.checkValidity()).toBeFalse();
    f!.requestSubmit();
    expect(calls.length).toBe(0);
    // editing the password after the confirm field must re-validate the confirm field too
    fill('password', GOOD + 'x');
    expect(f!.checkValidity()).toBeTrue();
  });

  it('calls activateInstitutionUser once with the fragment token and navigates to /workbench', async () => {
    const calls: string[][] = [];
    const { harness, f, fill } = await setup(`/activate#token=${TOKEN}`, undefined, calls);
    fill('password', GOOD);
    fill('confirm', GOOD);
    f!.requestSubmit();
    await harness.fixture.whenStable();
    expect(calls).toEqual([[TOKEN, GOOD]]);
    expect(TestBed.inject(Router).url).toBe('/workbench');
  });

  it('shows an activation-specific sentence on 401', async () => {
    const { harness, root, f, fill } = await setup(`/activate#token=${TOKEN}`, { status: 401, error: { detail: 'Invalid or expired token' } });
    fill('password', GOOD);
    fill('confirm', GOOD);
    f!.requestSubmit();
    harness.detectChanges();
    const alert = root.querySelector('[role="alert"]');
    expect(alert?.textContent?.trim()).toBe('This activation link is invalid or has expired. Ask for a new one.');
  });

  it('shows the rate-limit sentence on 429', async () => {
    const { harness, root, f, fill } = await setup(`/activate#token=${TOKEN}`, { status: 429, error: { detail: 'x' } });
    fill('password', GOOD);
    fill('confirm', GOOD);
    f!.requestSubmit();
    harness.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent?.trim()).toBe('Too many attempts. Please wait a minute and try again.');
  });

  it('shows the server sentence for a weak password (400) and keeps the form for a retry', async () => {
    const { harness, root, f, fill } = await setup(`/activate#token=${TOKEN}`, { status: 400, error: { detail: 'Password must be at least 10 characters' } });
    fill('password', GOOD);
    fill('confirm', GOOD);
    f!.requestSubmit();
    harness.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Password must be');
    expect(root.querySelector('form')).toBeTruthy();
    expect((root.querySelector('button[type="submit"]') as HTMLButtonElement).disabled).toBeFalse();
  });
});
