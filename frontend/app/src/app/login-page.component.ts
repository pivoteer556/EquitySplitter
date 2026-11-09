import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

@Component({
  selector: 'app-login-page',
  imports: [CommonModule, FormsModule],
  templateUrl: './login-page.component.html',
  styleUrl: './login-page.component.css',
})
export class LoginPageComponent {
  loginEmail = '';
  loginPassword = '';

  error = '';
  loading = false;

  constructor(
    private readonly api: ApiService,
    private readonly router: Router,
  ) {}

  registerError = '';
  registerLoading = false;

  /**
   * One form for every account (BACKLOG 2n). Try the user login (owner/buyer/platform admin) first, then the
   * institution login (officer). If an email exists as both kinds the user account wins; choosing between them is a
   * separate, later item. Rate limits hold: the server keys each kind separately ("user:" / "institution:" +
   * ip + email), so every wrong guess is counted in both buckets and nothing gets more attempts than before. A user-side
   * 429 therefore does not stop the institution attempt (an officer must not be locked out by their own bucket
   * of failed user probes); if that also fails, the 429 is what we report.
   * Routing: the token carries no platform-admin flag, so admins land on /listings like any user and open /bootstrap
   * themselves (its server gate is unchanged).
   */
  login(): void {
    this.error = '';
    this.loading = true;
    const { loginEmail: email, loginPassword: password } = this; // the SUBMITTED credentials, even if the fields are edited while pending
    this.api.ownerLogin(email, password).subscribe({
      next: () => this.router.navigateByUrl('/listings'),
      error: (userErr) => {
        const status = (userErr as { status?: number })?.status;
        if (status !== 401 && status !== 429) {
          this.fail(userErr);
          return;
        }
        this.api.institutionLogin(email, password).subscribe({
          next: () => this.router.navigateByUrl('/workbench'),
          error: (instErr) => this.fail(status === 429 ? userErr : instErr),
        });
      },
    });
  }

  private fail(err: unknown): void {
    this.error = friendlyError(err);
    this.loading = false;
  }

  // Moved unchanged from the old /buyer page: same fields, same endpoint, no buy/sell/work chooser yet.
  register(name: string, email: string, password: string): void {
    this.registerError = '';
    this.registerLoading = true;
    this.api.ownerRegister({ name, email, password }).subscribe({
      next: () => this.router.navigateByUrl('/listings'),
      error: (err) => {
        this.registerError = friendlyError(err);
        this.registerLoading = false;
      },
    });
  }
}
