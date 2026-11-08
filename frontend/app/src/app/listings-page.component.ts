import { DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { friendlyError } from './error-message';
import { Listing } from './models';

const PAGE_SIZE = 20;
const STATUS_TEXT: Record<string, string> = { pending_acknowledgement: 'Awaiting owner sign-off' };

@Component({
  selector: 'app-listings-page',
  imports: [DatePipe, RouterLink],
  templateUrl: './listings-page.component.html',
})
export class ListingsPageComponent implements OnInit {
  listings: Listing[] = [];
  loading = true;
  hasMore = false;
  error = '';
  unauthorized = false;

  constructor(private readonly api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.getListings(PAGE_SIZE, this.listings.length).subscribe({
      next: (page) => {
        this.listings = [...this.listings, ...page];
        this.hasMore = page.length >= PAGE_SIZE;
        this.loading = false;
      },
      error: (err) => {
        this.unauthorized = err?.status === 401;
        this.error = friendlyError(err, 'Please sign in to see listings.');
        this.loading = false;
      },
    });
  }

  statusText(status: string): string {
    return STATUS_TEXT[status] ?? 'Pending';
  }
}
