import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

@Component({
  selector: 'app-bootstrap-page',
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './bootstrap-page.component.html',
  styleUrl: './bootstrap-page.component.css',
})
export class BootstrapPageComponent {
  institutionName = '';
  officerName = '';
  officerEmail = '';
  setupToken = ''; // memory only: cleared after every attempt, never persisted
  activationLink = '';

  error = '';
  loading = false;
  // Platform admins sign in with the user sign-in (/buyer) until the unified login (BACKLOG 2n step 3).
  signedIn = false;

  constructor(private readonly api: ApiService) {
    this.signedIn = !!api.getUserToken();
  }

  bootstrapInstitution(): void {
    if (!this.signedIn) {
      return;
    }
    this.error = '';
    this.activationLink = '';
    this.loading = true;
    const token = this.setupToken;
    this.setupToken = '';
    this.api.bootstrapInstitution({
      institutionName: this.institutionName,
      officerName: this.officerName,
      officerEmail: this.officerEmail,
    }, token).subscribe({
      next: (res) => {
        // No session yet: the officer activates through this link and then signs in.
        this.activationLink = window.location.origin + res.activationPath;
        this.loading = false;
      },
      error: (err) => {
        // A bad setup token and a missing or non-admin session are the same generic 404; name both, say which failed for neither.
        this.error = err?.status === 404 ? 'Not accepted. Sign in as platform admin and check the setup token.' : friendlyError(err);
        this.loading = false;
      },
    });
  }
}
