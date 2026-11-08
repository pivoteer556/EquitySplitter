import { Component, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';

@Component({
  selector: 'app-buyer-page',
  imports: [RouterLink],
  templateUrl: './buyer-page.component.html',
})
export class BuyerPageComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  signInError = '';
  signInLoading = false;
  registerError = '';
  registerLoading = false;

  signIn(email: string, password: string): void {
    this.signInError = '';
    this.signInLoading = true;
    this.api.ownerLogin(email, password).subscribe({
      next: () => this.router.navigateByUrl('/listings'),
      error: (err) => {
        this.signInError = friendlyError(err);
        this.signInLoading = false;
      },
    });
  }

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
