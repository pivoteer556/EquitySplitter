import { TestBed } from '@angular/core/testing';

import { HouseIllustrationComponent } from './house-illustration.component';

describe('HouseIllustrationComponent', () => {
  function setup(inputs: { label?: string; decorative?: boolean; maxWidth?: string } = {}) {
    TestBed.configureTestingModule({ imports: [HouseIllustrationComponent] });
    const fixture = TestBed.createComponent(HouseIllustrationComponent);
    Object.assign(fixture.componentInstance as object, inputs);
    fixture.detectChanges();
    const host = fixture.nativeElement as HTMLElement;
    return { host, svg: host.querySelector('svg')! };
  }

  it('renders an svg with the 400 x 260 viewBox', () => {
    const { svg } = setup();
    expect(svg).not.toBeNull();
    expect(svg.getAttribute('viewBox')).toBe('0 0 400 260');
  });

  it('is a labelled image by default', () => {
    const { svg } = setup();
    expect(svg.getAttribute('role')).toBe('img');
    expect(svg.getAttribute('aria-label')).toBe('Illustration of a suburban house');
    expect(svg.getAttribute('aria-hidden')).toBeNull();
  });

  it('uses a custom label when given', () => {
    const { svg } = setup({ label: 'Illustration of 418 Larkspur Court' });
    expect(svg.getAttribute('aria-label')).toBe('Illustration of 418 Larkspur Court');
  });

  it('is hidden from assistive technology when decorative', () => {
    const { svg } = setup({ decorative: true });
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('role')).toBeNull();
    expect(svg.getAttribute('aria-label')).toBeNull();
  });

  it('takes every colour from --house-* tokens, never a raw value', () => {
    const { svg } = setup();
    const painted = Array.from(svg.querySelectorAll('[fill], [stroke]')).flatMap((el) => [el.getAttribute('fill'), el.getAttribute('stroke')]).filter((v): v is string => !!v && v !== 'none');
    expect(painted.length).toBeGreaterThan(10);
    for (const value of painted) {
      expect(value).toMatch(/^var\(--house-[a-z-]+\)$/);
    }
    expect(svg.outerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgba?\(/);
  });

  it('resolves the tokens to real colours from the global styles', () => {
    const { host, svg } = setup();
    document.body.appendChild(host);
    const lawn = svg.querySelector('[fill="var(--house-lawn)"]')!;
    expect(getComputedStyle(lawn).fill).not.toBe('none');
    expect(getComputedStyle(lawn).fill).toBe('rgb(107, 154, 91)'); // --house-lawn #6B9A5B
    host.remove();
  });

  it('scales with its container: no fixed width or height attributes', () => {
    const { svg } = setup();
    expect(svg.hasAttribute('width')).toBeFalse();
    expect(svg.hasAttribute('height')).toBeFalse();
    expect(svg.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
    expect(getComputedStyle(svg).width).not.toBe('0px');
  });

  it('does not cap the width by default', () => {
    expect(setup().svg.style.maxWidth).toBe('');
  });

  it('caps the width when maxWidth is given', () => {
    expect(setup({ maxWidth: '320px' }).svg.style.maxWidth).toBe('320px');
  });
});
