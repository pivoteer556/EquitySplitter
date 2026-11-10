import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { SecurityPageComponent } from './security-page.component';

const EIGHT = ['AAAAA-BBBBB', 'CCCCC-DDDDD', 'EEEEE-FFFFF', 'GGGGG-HHHHH', 'JJJJJ-KKKKK', 'LLLLL-MMMMM', 'NNNNN-PPPPP', 'QQQQQ-RRRRR'];

describe('SecurityPageComponent', () => {
  // err === null means success; otherwise the api call fails with err.
  function setup(err: unknown = null, calls: string[] = []) {
    const api = {
      regenerateRecoveryCodes: (code: string) => {
        calls.push(code);
        return err === null ? of({ recoveryCodes: EIGHT }) : throwError(() => err);
      },
    };
    TestBed.configureTestingModule({
      imports: [SecurityPageComponent],
      providers: [{ provide: ApiService, useValue: api }, provideRouter([])],
    });
    const fixture = TestBed.createComponent(SecurityPageComponent);
    fixture.detectChanges();
    return fixture;
  }

  async function typeCode(fixture: ReturnType<typeof setup>, value: string) {
    await fixture.whenStable(); // ngModel writes its initial empty value asynchronously; let that land first
    const input = (fixture.nativeElement as HTMLElement).querySelector('#security-code') as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  const q = (fixture: ReturnType<typeof setup>, sel: string) => (fixture.nativeElement as HTMLElement).querySelector(sel);

  it('renders a heading, a code field and a disabled submit button, with no codes or error', () => {
    const fixture = setup();
    expect(q(fixture, 'h1')?.textContent).toContain('Security');
    expect(q(fixture, '#security-code')).toBeTruthy();
    expect((q(fixture, '#security-submit') as HTMLButtonElement).disabled).toBeTrue();
    expect(q(fixture, '#security-codes')).toBeNull();
    expect(q(fixture, '#security-error')).toBeNull();
  });

  it('enables submit only for exactly 6 digits', async () => {
    const fixture = setup();
    const submit = q(fixture, '#security-submit') as HTMLButtonElement;
    for (const bad of ['12345', '1234567', '12345a', '12 456']) {
      await typeCode(fixture, bad);
      expect(submit.disabled).withContext(bad).toBeTrue();
    }
    await typeCode(fixture, '123456');
    expect(submit.disabled).toBeFalse();
  });

  it('does not call the api when the code is not 6 digits', async () => {
    const calls: string[] = [];
    const fixture = setup(null, calls);
    await typeCode(fixture, '12345');
    fixture.componentInstance.regenerate();
    expect(calls).toEqual([]);
  });

  it('sends the typed code and shows exactly 8 fresh codes', async () => {
    const calls: string[] = [];
    const fixture = setup(null, calls);
    await typeCode(fixture, '123456');
    (q(fixture, '#security-submit') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(calls).toEqual(['123456']);
    const items = (fixture.nativeElement as HTMLElement).querySelectorAll('#security-codes li');
    expect(items.length).toBe(8);
    expect(items[0].textContent?.trim()).toBe('AAAAA-BBBBB');
    expect(q(fixture, '#security-error')).toBeNull();
  });

  it('shows a plain error on 401 and no codes', async () => {
    const fixture = setup({ status: 401, error: { detail: 'Invalid credentials' } });
    await typeCode(fixture, '123456');
    fixture.componentInstance.regenerate();
    fixture.detectChanges();
    expect(q(fixture, '#security-error')?.textContent).toContain('Incorrect or expired code');
    expect(q(fixture, '#security-codes')).toBeNull();
  });

  it('shows a readable message on 429', async () => {
    const fixture = setup({ status: 429, error: { detail: 'Too many' } });
    await typeCode(fixture, '123456');
    fixture.componentInstance.regenerate();
    fixture.detectChanges();
    expect(q(fixture, '#security-error')?.textContent).toContain('Too many attempts');
    expect(q(fixture, '#security-codes')).toBeNull();
  });
});
