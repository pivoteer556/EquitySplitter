import { Component, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

const INVALID_LINK = 'This activation link is invalid or has expired. Ask for a new one.';

@Component({
  selector: 'app-activate-page',
  templateUrl: './activate-page.component.html',
  styleUrl: './activate-page.component.css',
})
export class ActivatePageComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  /** Read once from the URL fragment; kept only in memory, never rendered or stored. */
  private readonly token =
    new URLSearchParams(inject(ActivatedRoute).snapshot.fragment ?? '').get('token') ?? '';

  readonly hasToken = this.token !== '';
  error = '';
  loading = false;

  constructor() {
    // Drop the fragment from the address bar and replace the history entry.
    this.router.navigate([], { relativeTo: inject(ActivatedRoute), replaceUrl: true });
  }

  activate(password: string): void {
    this.error = '';
    this.loading = true;
    this.api.activateInstitutionUser(this.token, password).subscribe({
      next: () => this.router.navigateByUrl('/workbench'),
      error: (err) => {
        this.error = friendlyError(err, INVALID_LINK);
        this.loading = false;
      },
    });
  }
}
