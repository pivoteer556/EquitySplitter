import { Component, Input } from '@angular/core';

// A suburban house for properties with no photo (docs/design/vertical-slice.md section 4). Inline SVG, so it can
// read the page's CSS custom properties; every colour is a --house-* token defined in styles.css.
@Component({
  selector: 'app-house-illustration',
  template: `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 400 260"
      preserveAspectRatio="xMidYMid meet"
      focusable="false"
      [attr.role]="decorative ? null : 'img'"
      [attr.aria-label]="decorative ? null : label"
      [attr.aria-hidden]="decorative ? 'true' : null"
      [style.max-width]="maxWidth || null"
    >
      <!-- ground and walk -->
      <rect x="0" y="205" width="400" height="55" fill="var(--house-lawn)" />
      <rect x="188" y="205" width="24" height="55" fill="var(--house-path)" />
      <polygon points="300,205 352,205 372,260 292,260" fill="var(--house-path)" />
      <!-- tree -->
      <rect x="42" y="150" width="9" height="58" fill="var(--house-trunk)" />
      <circle cx="46" cy="132" r="34" fill="var(--house-tree)" />
      <circle cx="60" cy="146" r="22" fill="var(--house-tree-dark)" />
      <!-- garage -->
      <rect x="290" y="150" width="86" height="55" fill="var(--house-wall)" stroke="var(--house-trim)" stroke-width="2" />
      <polygon points="282,153 333,128 384,153" fill="var(--house-roof)" />
      <rect x="302" y="168" width="62" height="37" fill="var(--house-trim)" />
      <path d="M302 177H364M302 186H364M302 195H364" stroke="var(--house-wall)" stroke-width="1.5" opacity="0.6" />
      <!-- main house -->
      <rect x="236" y="62" width="16" height="34" fill="var(--house-trim)" />
      <rect x="110" y="118" width="180" height="87" fill="var(--house-wall)" stroke="var(--house-trim)" stroke-width="2" />
      <polygon points="98,123 200,56 302,123" fill="var(--house-roof)" />
      <circle cx="200" cy="96" r="10" fill="var(--house-glass)" stroke="var(--house-wall)" stroke-width="3" />
      <!-- windows -->
      <g fill="var(--house-glass)" stroke="var(--house-wall)" stroke-width="3">
        <rect x="126" y="142" width="34" height="32" />
        <rect x="240" y="142" width="34" height="32" />
      </g>
      <path d="M143 142V174M126 158H160M257 142V174M240 158H274" stroke="var(--house-wall)" stroke-width="2" />
      <!-- porch and door -->
      <rect x="176" y="150" width="48" height="6" fill="var(--house-trim)" />
      <rect x="186" y="156" width="28" height="49" fill="var(--house-door)" />
      <circle cx="208" cy="182" r="2" fill="var(--house-roof)" />
      <rect x="172" y="198" width="56" height="7" fill="var(--house-trim)" />
    </svg>
  `,
  styles: `
    svg {
      display: block;
      width: 100%;
      height: auto;
    }
  `,
})
export class HouseIllustrationComponent {
  @Input() label = 'Illustration of a suburban house';
  @Input() decorative = false; // set when a caption or the address is already next to it
  @Input() maxWidth = ''; // any CSS length, e.g. '320px'; empty means fill the container
}
