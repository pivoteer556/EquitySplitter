import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';
import { HouseIllustrationComponent } from './house-illustration.component';
import { Property, PropertyDetailResponse, PropertyOwnerStatus } from './models';

// The owner's "my home" page (docs/design/vertical-slice.md section 5). Reads only: GET /properties, then the detail
// and owners of the chosen property, all signed with the buyer's token. The stage statement is plain language, one case per stage (S6).
@Component({
  selector: 'app-home-page',
  imports: [CurrencyPipe, DatePipe, DecimalPipe, RouterLink, HouseIllustrationComponent],
  templateUrl: './home-page.component.html',
  styleUrl: './home-page.component.css',
})
export class HomePageComponent implements OnInit {
  properties: Property[] = [];
  detail: PropertyDetailResponse | null = null;
  owners: PropertyOwnerStatus[] = [];
  loading = true;
  error = '';

  constructor(private readonly api: ApiService) {}

  ngOnInit(): void {
    this.api.getProperties().subscribe({
      next: (properties) => {
        this.properties = properties;
        if (properties.length) this.choose(properties[0]);
        else this.loading = false;
      },
      error: (err) => this.fail(err),
    });
  }

  choose(property: Property): void {
    this.loading = true;
    this.error = '';
    forkJoin([this.api.getProperty(property.id, 'user'), this.api.getOwners(property.id, 'user')]).subscribe({
      next: ([detail, owners]) => {
        this.detail = detail;
        this.owners = owners.owners;
        this.loading = false;
      },
      error: (err) => this.fail(err),
    });
  }

  /** Sum of the owners' down payments in cents, or null while any owner has none recorded. */
  get totalDownPayments(): number | null {
    if (!this.owners.length || this.owners.some((o) => o.downPaymentAmount === null)) return null;
    const cents = this.owners.reduce((sum, o) => sum + Math.round(Number(o.downPaymentAmount) * 100), 0);
    return cents / 100;
  }

  plain(value: string): string {
    return value.replace(/_/g, ' ');
  }

  private fail(err: unknown): void {
    this.error = friendlyError(err, 'Please sign in to see your home.');
    this.loading = false;
  }
}
