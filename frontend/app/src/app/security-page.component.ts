import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

/**
 * Signed-in officer security page (BACKLOG 2l step 3d). Route-guarded by officerGuard.
 * Typing a current 6-digit authenticator code replaces the officer's recovery codes; the 8 new ones are shown once
 * and held only in memory (a reload loses them, by design).
 */
@Component({
  selector: 'app-security-page',
  imports: [FormsModule],
  templateUrl: './security-page.component.html',
  styleUrl: './security-page.component.css',
})
export class SecurityPageComponent {
  code = '';
  recoveryCodes: string[] | null = null;
  error = '';
  loading = false;

  constructor(private readonly api: ApiService) {}

  get codeValid(): boolean {
    return /^\d{6}$/.test(this.code);
  }

  regenerate(): void {
    if (!this.codeValid || this.loading) return;
    this.error = '';
    this.recoveryCodes = null;
    this.loading = true;
    const { code } = this; // the SUBMITTED code, even if the field is edited while pending
    this.api.regenerateRecoveryCodes(code).subscribe({
      next: (res) => {
        this.recoveryCodes = res.recoveryCodes;
        this.code = '';
        this.loading = false;
      },
      // 401 text is generic on purpose: wrong, replayed and expired codes look the same. 429 uses the shared friendlyError text.
      error: (err) => {
        this.error = friendlyError(err, 'Incorrect or expired code. Check your authenticator app and try again.');
        this.loading = false;
      },
    });
  }
}
