import { TestBed } from '@angular/core/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the router outlet (pages supply their own headings)', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });

  it('renders the lockup logo inline in the brand header with an accessible name', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header.brand');
    expect(header).not.toBeNull();
    const logo = header!.querySelector('svg.logo[role="img"]');
    expect(logo).not.toBeNull();
    expect(logo!.getAttribute('aria-label')).toBe('EquitySplitter');
    // Both halves of the split "Splitter" exist, and the mark's three shares.
    expect(logo!.querySelectorAll('.logo-navy').length).toBeGreaterThanOrEqual(2);
    expect(logo!.querySelectorAll('.logo-blue').length).toBeGreaterThanOrEqual(2);
    expect(logo!.querySelectorAll('.logo-amber').length).toBe(1);
  });

  it('draws the logo from brand tokens and keeps it legible on the page color', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const logo = (fixture.nativeElement as HTMLElement).querySelector('header.brand svg.logo')!;
    const bg = getComputedStyle(document.body).backgroundColor;
    const lum = (rgb: string) => {
      const [r, g, b] = (rgb.match(/\d+/g) ?? []).slice(0, 3).map((v) => {
        const c = Number(v) / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const ratio = (a: string, b: string) => {
      const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const fillOf = (sel: string) => getComputedStyle(logo.querySelector(sel)!).fill;
    // Tokens: navy #14213D, amber #E0A800 (blue may be --brand-blue or a darker token, so only its contrast is pinned).
    expect(fillOf('.logo-navy')).toBe('rgb(20, 33, 61)');
    expect(fillOf('.logo-amber')).toBe('rgb(224, 168, 0)');
    // Depends on the page color token (Melchior): navy text-like parts need 4.5:1, blue graphics 3:1.
    for (const el of Array.from(logo.querySelectorAll('.logo-navy'))) {
      expect(ratio(getComputedStyle(el).fill, bg)).toBeGreaterThanOrEqual(4.5);
    }
    for (const el of Array.from(logo.querySelectorAll('.logo-blue'))) {
      expect(ratio(getComputedStyle(el).fill, bg)).toBeGreaterThanOrEqual(3);
    }
  });
});
