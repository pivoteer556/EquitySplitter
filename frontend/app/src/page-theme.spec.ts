// Global page theme (styles.css): light blue page, navy text directly on it, cream cards.
function luminance(rgb: string): number {
  const [r, g, b] = (rgb.match(/\d+/g) ?? []).slice(0, 3).map((v) => {
    const c = Number(v) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('page theme (light blue page)', () => {
  it('puts a light blue background on the page with navy text that reads on it', () => {
    const body = getComputedStyle(document.body);
    expect(body.backgroundColor).toBe('rgb(159, 196, 238)'); // --brand-page #9FC4EE
    expect(body.color).toBe('rgb(20, 33, 61)'); // --brand-navy
    expect(body.color).not.toBe(body.backgroundColor);
    expect(contrast(body.color, body.backgroundColor)).toBeGreaterThanOrEqual(4.5);
  });

  it('keeps a page-level heading and link readable on the light blue page', () => {
    const host = document.createElement('main');
    host.innerHTML = '<h1>Title</h1><a href="/x">link</a>';
    document.body.appendChild(host);
    const bg = getComputedStyle(document.body).backgroundColor;
    for (const sel of ['h1', 'a']) {
      const color = getComputedStyle(host.querySelector(sel)!).color;
      expect(color).not.toBe(bg);
      expect(contrast(color, bg)).toBeGreaterThanOrEqual(4.5);
    }
    host.remove();
  });
});
