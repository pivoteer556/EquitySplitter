import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

@Component({
  selector: 'app-bootstrap-page',
  imports: [CommonModule, FormsModule],
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

  constructor(private readonly api: ApiService) {}

  bootstrapInstitution(): void {
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
        // A wrong or missing setup token is a generic 404 from the server; do not say whether the endpoint exists.
        this.error = err?.status === 404 ? 'Setup token not accepted.' : friendlyError(err);
        this.loading = false;
      },
    });
  }
}
