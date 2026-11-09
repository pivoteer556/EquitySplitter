import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from './api.service';
import { PropertyOwnerStatus } from './models';

@Component({
  selector: 'app-workbench-page',
  imports: [CommonModule, FormsModule],
  templateUrl: './workbench-page.component.html',
  styleUrl: './workbench-page.component.css',
})
export class WorkbenchPageComponent {
  institutionToken = '';
  userToken = '';
  institutionId = '';
  propertyAddress = '';
  loanAmount = 0;
  currentBalance = 0;
  monthlyPayment = 0;
  dynamicBillingEnabled = false;
  propertyId = '';

  noticeDays = 30;
  valuationMethod = 'equity_balance';
  partialClaimMethod = 'pro_rata';

  ownerName = '';
  ownerEmail = '';
  inviteLink = '';
  maxOwnershipPercent: number | null = null;

  propertyStatus = '';
  agreementEffectiveAt = '';
  owners: PropertyOwnerStatus[] = [];

  lastResponse = '';
  error = '';

  constructor(
    private readonly api: ApiService,
    private readonly router: Router,
  ) {
    this.institutionToken = this.api.getInstitutionToken();
    this.userToken = this.api.getUserToken();
    this.institutionId = this.api.getInstitutionId();
  }

  logout(): void {
    this.api.clearTokens();
    this.router.navigateByUrl('/login');
  }

  clearMessages(): void {
    this.error = '';
    this.lastResponse = '';
  }

  setError(err: unknown): void {
    const e = err as { error?: unknown; message?: string };
    this.error = JSON.stringify(e.error ?? e.message ?? err, null, 2);
  }

  refreshTokens(): void {
    this.institutionToken = this.api.getInstitutionToken();
    this.userToken = this.api.getUserToken();
    this.institutionId = this.api.getInstitutionId();
  }

  createProperty(): void {
    this.clearMessages();
    this.api.createProperty({
      institutionId: this.institutionId,
      address: this.propertyAddress,
      loanAmount: this.loanAmount,
      currentBalance: this.currentBalance,
      monthlyPayment: this.monthlyPayment,
      dynamicBillingEnabled: this.dynamicBillingEnabled,
    }).subscribe({
      next: (res) => {
        this.propertyId = res.id;
        this.propertyStatus = res.status;
        this.lastResponse = JSON.stringify(res, null, 2);
      },
      error: (err) => this.setError(err),
    });
  }

  attachAgreement(): void {
    this.clearMessages();
    this.api.attachAgreement(this.propertyId, {
      noticeDays: this.noticeDays,
      valuationMethod: this.valuationMethod,
      partialClaimMethod: this.partialClaimMethod,
    }).subscribe({
      next: (res) => {
        this.agreementEffectiveAt = res.effectiveAt ?? '';
        this.lastResponse = JSON.stringify(res, null, 2);
      },
      error: (err) => this.setError(err),
    });
  }

  inviteOwner(): void {
    this.clearMessages();
    this.inviteLink = '';
    this.api.inviteOwner(this.propertyId, {
      name: this.ownerName,
      email: this.ownerEmail,
      maxOwnershipPercent: this.maxOwnershipPercent,
    }).subscribe({
      next: (res) => {
        const { inviteToken, ...rest } = res;
        this.inviteLink = inviteToken ? `${window.location.origin}/accept-invite#token=${inviteToken}` : '';
        this.lastResponse = JSON.stringify(rest, null, 2);
        this.refreshOwners();
      },
      error: (err) => this.setError(err),
    });
  }

  acknowledgeAsOwner(): void {
    this.clearMessages();
    this.api.acknowledge(this.propertyId).subscribe({
      next: (res) => {
        this.lastResponse = JSON.stringify(res, null, 2);
        this.refreshProperty();
        this.refreshOwners();
      },
      error: (err) => this.setError(err),
    });
  }

  refreshProperty(): void {
    this.clearMessages();
    this.api.getProperty(this.propertyId).subscribe({
      next: (res) => {
        this.propertyStatus = res.property.status;
        this.agreementEffectiveAt = res.agreement?.effectiveAt ?? '';
        this.lastResponse = JSON.stringify(res, null, 2);
      },
      error: (err) => this.setError(err),
    });
  }

  refreshOwners(): void {
    this.clearMessages();
    this.api.getOwners(this.propertyId).subscribe({
      next: (res) => {
        this.owners = res.owners;
      },
      error: (err) => this.setError(err),
    });
  }
}
