import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { BootstrapPageComponent } from './bootstrap-page.component';

describe('BootstrapPageComponent', () => {
  function setup(err: unknown, bootstrapCalls: Record<string, string>[] = []) {
    const api = {
      bootstrapInstitution: (payload: Record<string, string>) => {
        bootstrapCalls.push(payload);
        return err === undefined
          ? of({ institution: { id: 'i' }, institutionUser: {}, activationToken: 'tok', activationPath: '/activate#token=tok' })
          : throwError(() => err);
      },
    };
    TestBed.configureTestingModule({
      imports: [BootstrapPageComponent],
      providers: [
        { provide: ApiService, useValue: api },
        provideRouter([]),
      ],
    });
    const fixture = TestBed.createComponent(BootstrapPageComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('draws the card as a cream surface with an amber border and a blue submit button', () => {
    const root = setup(undefined).nativeElement as HTMLElement;
    const card = getComputedStyle(root.querySelector('.bootstrap-shell')!);
    expect(card.backgroundColor).toBe('rgb(248, 237, 203)'); // --brand-surface #F8EDCB
    expect(card.borderTopColor).toBe('rgb(217, 185, 106)'); // --brand-border #D9B96A
    expect(card.backgroundColor).not.toBe(getComputedStyle(document.body).backgroundColor);
    expect(getComputedStyle(root.querySelector('button[type=submit]')!).backgroundColor).toBe('rgb(58, 95, 176)');
    expect(getComputedStyle(root.querySelector('h1')!).color).toBe('rgb(20, 33, 61)');
  });

  it('shows the Bootstrap New Institution form and no sign-in form', () => {
    const root = setup(undefined).nativeElement as HTMLElement;
    expect(root.querySelector('h1')?.textContent).toContain('Bootstrap New Institution');
    expect(root.querySelector('#bootstrap-form')).toBeTruthy();
    expect(root.querySelector('#signin-form')).toBeNull();
  });

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

  it('shows a plain sentence when bootstrap fails with no connection', () => {
    const fixture = setup({ status: 0, error: new ProgressEvent('error') });
    fixture.componentInstance.bootstrapInstitution();
    fixture.detectChanges();
    const el = (fixture.nativeElement as HTMLElement).querySelector('.error');
    expect(el?.textContent?.trim()).toBe(
      "Can't reach the server. Check your connection and try again.",
    );
  });

  describe('bootstrap form', () => {
    async function bform(err: unknown = undefined, bootstrapCalls: Record<string, string>[] = []) {
      const fixture = setup(err, bootstrapCalls);
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
});
