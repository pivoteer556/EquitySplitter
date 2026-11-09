import { Component, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

const INVALID_INVITE = 'This invite link is invalid or has expired. Ask for a new invite.';

@Component({
  selector: 'app-accept-invite-page',
  templateUrl: './accept-invite-page.component.html',
  styleUrl: './accept-invite-page.component.css',
})
export class AcceptInvitePageComponent {
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

  accept(password: string): void {
    this.error = '';
    this.loading = true;
    this.api.acceptInvite(this.token, password).subscribe({
      next: () => this.router.navigateByUrl('/listings'),
      error: (err) => {
        this.error = friendlyError(err, INVALID_INVITE);
        this.loading = false;
      },
    });
  }
}
