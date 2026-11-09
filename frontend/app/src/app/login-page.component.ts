import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';
import { LoginResponse, TotpEnrollment } from './models';

@Component({
  selector: 'app-login-page',
  imports: [CommonModule, FormsModule],
  templateUrl: './login-page.component.html',
  styleUrl: './login-page.component.css',
})
export class LoginPageComponent {
  loginEmail = '';
  loginPassword = '';
  loginCode = '';
  challengeToken = ''; // set only after the password step asked for an authenticator code
  enrolCode = '';
  enrolChallengeToken = ''; // set only when the officer has no authenticator yet and must enrol
  enrolment: TotpEnrollment | null = null;

  error = '';
  loading = false;

  constructor(
    private readonly api: ApiService,
    private readonly router: Router,
  ) {}

  registerError = '';
  registerLoading = false;

  /**
   * One form, one request (BACKLOG 2n): POST /auth/login signs in any account and says which kind it was.
   * Officer -> /workbench, platform admin -> /bootstrap, any other user -> /listings.
   */
  login(): void {
    this.error = '';
    this.loading = true;
    const { loginEmail: email, loginPassword: password } = this; // the SUBMITTED credentials, even if the fields are edited while pending
    this.api.login(email, password).subscribe({
      next: (res) => {
        if ('secondFactorRequired' in res) {
          this.challengeToken = res.challengeToken;
          this.loading = false;
          return;
        }
        if ('enrolmentRequired' in res) {
          this.startEnrolment(res.challengeToken);
          return;
        }
        this.finish(res);
      },
      error: (err) => this.fail(err),
    });
  }

  private startEnrolment(challengeToken: string): void {
    this.enrolChallengeToken = challengeToken;
    this.api.enrolStart(challengeToken).subscribe({
      next: (res) => {
        this.enrolment = res;
        this.loading = false;
      },
      error: (err) => {
        this.enrolChallengeToken = '';
        this.fail(err);
      },
    });
  }

  submitEnrolment(): void {
    this.error = '';
    this.loading = true;
    const { enrolChallengeToken: challengeToken, enrolCode: code } = this; // the SUBMITTED values, even if edited while pending
    this.api.enrolConfirm(challengeToken, code).subscribe({
      next: (res) => this.finish(res),
      error: (err) => this.fail(err, 'Incorrect or expired code. Check your authenticator app and try again.'),
    });
  }

  submitCode(): void {
    this.error = '';
    this.loading = true;
    const { challengeToken, loginCode: code } = this; // the SUBMITTED values, even if edited while pending
    this.api.loginTotp(challengeToken, code).subscribe({
      next: (res) => this.finish(res),
      error: (err) => this.fail(err, 'Incorrect or expired code. Check your authenticator app and try again.'),
    });
  }

  private finish(res: LoginResponse): void {
    this.router.navigateByUrl(res.userType === 'institution_user' ? '/workbench' : res.isPlatformAdmin ? '/bootstrap' : '/listings');
  }

  private fail(err: unknown, unauthorized?: string): void {
    this.error = friendlyError(err, unauthorized);
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
