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

  it('should render the brand header with the logo mark and the two-weight wordmark', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header.brand');
    expect(header).not.toBeNull();
    const mark = header!.querySelector('svg[role="img"]');
    expect(mark?.getAttribute('aria-label')).toBe(
      'EquitySplitter logo mark: a house divided into three unequal shares',
    );
    expect(header!.querySelector('.brand-equity')?.textContent).toBe('Equity');
    expect(header!.querySelector('.brand-splitter')?.textContent).toBe('Splitter');
  });

  it('draws the header and logo so they are visible on the night page', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const header = (fixture.nativeElement as HTMLElement).querySelector('header.brand')!;
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
    const text = getComputedStyle(header).color;
    expect(text).not.toBe(bg);
    expect(ratio(text, bg)).toBeGreaterThanOrEqual(4.5);
    for (const part of ['.share-navy', '.share-blue']) {
      const fill = getComputedStyle(header.querySelector(part)!).fill;
      expect(fill).not.toBe(bg);
      expect(ratio(fill, bg)).toBeGreaterThanOrEqual(3);
    }
  });
});
