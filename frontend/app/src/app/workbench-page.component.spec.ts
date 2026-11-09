import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { ApiService } from './api.service';
import { WorkbenchPageComponent } from './workbench-page.component';

describe('WorkbenchPageComponent owner access', () => {
  function setup(inviteToken: string | null = 'tok.en.value') {
    const api = {
      getInstitutionToken: () => 'inst',
      getUserToken: () => '',
      getInstitutionId: () => 'inst-1',
      clearTokens: () => undefined,
      inviteOwner: () =>
        of({ id: 'a', agreementId: 'g', userPropertyId: 'u', signedAt: null, inviteToken }),
      getOwners: () => of({ owners: [] }),
    };
    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: api }, provideRouter([])],
    });
    const fixture = TestBed.createComponent(WorkbenchPageComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('never asks the officer to type a password for an owner', () => {
    const root = setup().nativeElement as HTMLElement;
    expect(root.querySelector('input[type="password"]')).toBeNull();
    const buttons = Array.from(root.querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).not.toContain('Register Owner');
    expect(buttons).not.toContain('Login Owner');
  });

  it('shows the accept-invite link after inviting an owner', () => {
    const fixture = setup();
    const c = fixture.componentInstance;
    c.propertyId = 'p-1';
    c.ownerName = 'Olive Owner';
    c.ownerEmail = 'olive@example.com';
    c.inviteOwner();
    fixture.detectChanges();
    const link = (fixture.nativeElement as HTMLElement).querySelector('#invite-link');
    expect(link?.textContent).toContain('/accept-invite#token=tok.en.value');
  });

  it('shows no link when the server returns no invite token', () => {
    const fixture = setup(null);
    const c = fixture.componentInstance;
    c.propertyId = 'p-1';
    c.inviteOwner();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('#invite-link')).toBeNull();
  });
});
