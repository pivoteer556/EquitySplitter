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
});
