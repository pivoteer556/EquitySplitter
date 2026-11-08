import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

@Component({
  selector: 'app-login-page',
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './login-page.component.html',
  styleUrl: './login-page.component.css',
})
export class LoginPageComponent {
  institutionName = 'Atlas Lending';
  officerName = 'Casey Officer';
  officerEmail = 'casey.officer@example.com';
  activationLink = '';

  loginEmail = '';
  loginPassword = '';

  error = '';
  lastResponse = '';
  loading = false;

  constructor(
    private readonly api: ApiService,
    private readonly router: Router,
  ) {}

  bootstrapInstitution(): void {
    this.error = '';
    this.lastResponse = '';
    this.activationLink = '';
    this.loading = true;
    this.api.bootstrapInstitution({
      institutionName: this.institutionName,
      officerName: this.officerName,
      officerEmail: this.officerEmail,
    }).subscribe({
      next: (res) => {
        // No session yet: the officer activates through this link and then signs in.
        this.activationLink = window.location.origin + res.activationPath;
        this.loading = false;
      },
      error: (err) => {
        this.error = friendlyError(err);
        this.loading = false;
      },
    });
  }

  login(): void {
    this.error = '';
    this.lastResponse = '';
    this.loading = true;
    this.api.institutionLogin(this.loginEmail, this.loginPassword).subscribe({
      next: (res) => {
        this.lastResponse = JSON.stringify(res, null, 2);
        this.loading = false;
        this.router.navigateByUrl('/workbench');
      },
      error: (err) => {
        this.error = friendlyError(err);
        this.loading = false;
      },
    });
  }
}
