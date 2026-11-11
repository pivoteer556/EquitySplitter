import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { HomePageComponent } from './home-page.component';
import { Property, PropertyDetailResponse, PropertyOwnersResponse } from './models';

const property = (id: string, address: string): Property => ({
  id,
  institutionId: 'inst-1',
  address,
  loanAmount: '388000.00',
  currentBalance: '388000.00',
  monthlyPayment: '2389.00',
  dynamicBillingEnabled: false,
  status: 'active',
  createdAt: '2026-10-01T00:00:00Z',
});

const detail: PropertyDetailResponse = {
  property: property('p-1', '12 Maple Lane'),
  agreement: { id: 'a-1', propertyId: 'p-1', noticeDays: 30, valuationMethod: 'appraisal', partialClaimMethod: 'pro_rata', effectiveAt: null },
  purchase: {
    stage: 'intent_to_proceed',
    purchasePrice: '485000.00',
    closingDate: '2026-12-18',
    applicationFiledAt: null,
    intentToProceedAt: null,
    closedAt: null,
    interestRatePercent: '6.250',
    termMonths: 360,
  },
  listing: { askingPrice: '485000.00', bedrooms: 4, bathrooms: '2.5', squareFeet: 2140, description: 'Sunny corner lot.' },
};

const owners: PropertyOwnersResponse = {
  owners: [
    { userPropertyId: 'u-1', userId: 'x-1', name: 'Olive Owner', email: 'o@example.com', maxOwnershipPercent: null, signedAt: '2026-11-01T00:00:00Z', downPaymentAmount: '60000.00', sharePercent: '60.000', estimatedMonthlyShare: '1433.40' },
    { userPropertyId: 'u-2', userId: 'x-2', name: 'Sam Second', email: 's@example.com', maxOwnershipPercent: null, signedAt: null, downPaymentAmount: '40000.00', sharePercent: '40.000', estimatedMonthlyShare: '955.60' },
  ],
};

describe('HomePageComponent', () => {
  function setup(opts: { properties?: Property[]; failWith?: Partial<HttpErrorResponse> } = {}) {
    const properties = opts.properties ?? [property('p-1', '12 Maple Lane')];
    const api = {
      getProperties: jasmine.createSpy('getProperties').and.returnValue(
        opts.failWith ? throwError(() => opts.failWith) : of(properties),
      ),
      getProperty: jasmine.createSpy('getProperty').and.returnValue(of(detail)),
      getOwners: jasmine.createSpy('getOwners').and.returnValue(of(owners)),
    };
    TestBed.configureTestingModule({ providers: [{ provide: ApiService, useValue: api }, provideRouter([])] });
    const fixture = TestBed.createComponent(HomePageComponent);
    fixture.detectChanges();
    return { api, root: fixture.nativeElement as HTMLElement, fixture };
  }

  it('renders the house card, the owners table and the terms table', () => {
    const { api, root } = setup();
    expect(api.getProperty).toHaveBeenCalledWith('p-1', 'user');
    expect(api.getOwners).toHaveBeenCalledWith('p-1', 'user');
    expect(root.querySelector('h1')?.textContent).toContain('12 Maple Lane');
    expect(root.querySelector('app-house-illustration')).not.toBeNull();
    const text = root.textContent ?? '';
    expect(text).toContain('4 bedrooms');
    expect(text).toContain('2.5 bathrooms');
    expect(text).toContain('2,140 sq ft');
    expect(text).toContain('Sunny corner lot.');
    expect(text).toContain('intent_to_proceed');

    const ownerRows = root.querySelectorAll('table.owners tbody tr');
    expect(ownerRows.length).toBe(2);
    expect(root.querySelector('table.owners caption')).not.toBeNull();
    expect(root.querySelector('table.owners th[scope="col"]')).not.toBeNull();
    const first = ownerRows[0].textContent ?? '';
    expect(first).toContain('Olive Owner');
    expect(first).toContain('$60,000.00');
    expect(first).toContain('60.000%');
    expect(first).toContain('$1,433.40');
    expect(first).toContain('Signed');
    expect(ownerRows[1].textContent).toContain('Not yet signed');

    const terms = (root.querySelector('table.terms') as HTMLElement).textContent ?? '';
    expect(terms).toContain('$485,000.00');
    expect(terms).toContain('$100,000.00');
    expect(terms).toContain('$388,000.00');
    expect(terms).toContain('6.250%');
    expect(terms).toContain('360 months');
    expect(terms).toContain('$2,389.00');
    expect(terms).toContain('Dec 18, 2026');

    expect(text).toContain('30 days');
    expect(text).toContain('Not yet effective');
  });

  it('shows a message and a link to /listings when the buyer has no properties', () => {
    const { api, root } = setup({ properties: [] });
    expect(api.getProperty).not.toHaveBeenCalled();
    expect(root.textContent).toContain('no property');
    expect(root.querySelector('a[href="/listings"]')).not.toBeNull();
  });

  it('shows the friendly error when the load fails', () => {
    const { root } = setup({ failWith: { status: 0 } });
    expect(root.querySelector('[role="alert"]')?.textContent).toContain("Can't reach the server");
  });

  it('lists several properties and loads the one chosen', () => {
    const { api, root, fixture } = setup({ properties: [property('p-1', '12 Maple Lane'), property('p-2', '9 Oak Road')] });
    const buttons = Array.from(root.querySelectorAll('nav button')) as HTMLButtonElement[];
    expect(buttons.map((b) => b.textContent?.trim())).toEqual(['12 Maple Lane', '9 Oak Road']);
    buttons[1].click();
    fixture.detectChanges();
    expect(api.getProperty).toHaveBeenCalledWith('p-2', 'user');
  });
});
