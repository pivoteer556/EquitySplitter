import { HttpClient, HttpHeaders, HttpParams, HttpResponse } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable, tap } from 'rxjs';

import { environment } from '../environments/environment';

import {
  Acknowledgement,
  AuthTokenResponse,
  EnrolmentChallenge,
  Institution,
  InstitutionBootstrapResponse,
  InstitutionUserCreated,
  Listing,
  LoginResponse,
  Property,
  PropertyAgreement,
  PropertyDetailResponse,
  PropertyOwnersResponse,
  SecondFactorChallenge,
  TotpEnrollment,
} from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;
  private readonly institutionTokenStorageKey = 'institutionToken';
  private readonly userTokenStorageKey = 'userToken';
  private readonly institutionIdStorageKey = 'institutionId';
  private institutionToken = localStorage.getItem(this.institutionTokenStorageKey) ?? '';
  private userToken = localStorage.getItem(this.userTokenStorageKey) ?? '';
  private institutionId = localStorage.getItem(this.institutionIdStorageKey) ?? '';

  constructor(private readonly http: HttpClient) {}

  bootstrapInstitution(payload: {
    institutionName: string;
    officerName: string;
    officerEmail: string;
  }, setupToken: string): Observable<InstitutionBootstrapResponse> {
    // No session comes back for the officer: they set a password by opening the activation link.
    // Two-part gate: the server's BOOTSTRAP_TOKEN (sent per request, never stored) plus the signed-in platform admin's
    // user token. The server rotates that session on success, so keep the refreshed token.
    const headers: Record<string, string> = { 'X-Bootstrap-Token': setupToken };
    if (this.userToken) {
      headers['Authorization'] = `Bearer ${this.userToken}`;
    }
    return this.http
      .post<InstitutionBootstrapResponse>(`${this.baseUrl}/auth/institution/bootstrap`, payload, { observe: 'response', headers })
      .pipe(map((res) => this.applyRefreshedToken(res, 'user')));
  }

  activateInstitutionUser(token: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.baseUrl}/auth/institution/activate`, { token, password }).pipe(
      tap((res) => {
        this.setInstitutionToken(res.accessToken);
        this.setInstitutionId(this.extractInstitutionId(res.accessToken));
      }),
    );
  }

  /** One sign-in for every account; userType in the response decides which stored token (officer or user) it becomes. */
  login(email: string, password: string): Observable<LoginResponse | SecondFactorChallenge | EnrolmentChallenge> {
    return this.http.post<LoginResponse | SecondFactorChallenge | EnrolmentChallenge>(`${this.baseUrl}/auth/login`, { email, password }).pipe(
      tap((res) => {
        if (!('secondFactorRequired' in res) && !('enrolmentRequired' in res)) this.storeLogin(res); // a challenge is not a session: store nothing
      }),
    );
  }

  /** Second sign-in step for an officer with an authenticator; stores the session exactly as login does. */
  loginTotp(challengeToken: string, code: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.baseUrl}/auth/login/totp`, { challengeToken, code }).pipe(tap((res) => this.storeLogin(res)));
  }

  /** First sign-in of an officer with no authenticator: ask for a (new) secret to show them. Stores nothing. */
  enrolStart(challengeToken: string): Observable<TotpEnrollment> {
    return this.http.post<TotpEnrollment>(`${this.baseUrl}/auth/login/totp/enroll-start`, { challengeToken });
  }

  /** Confirms the first code; the answer is a normal login, stored exactly as login does. */
  enrolConfirm(challengeToken: string, code: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.baseUrl}/auth/login/totp/enroll-confirm`, { challengeToken, code }).pipe(tap((res) => this.storeLogin(res)));
  }

  private storeLogin(res: LoginResponse): void {
    if (res.userType === 'institution_user') {
      this.setInstitutionToken(res.accessToken);
      this.setInstitutionId(res.institutionId ?? '');
    } else {
      this.setUserToken(res.accessToken);
    }
  }

  ownerRegister(payload: { name: string; email: string; password: string }): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.baseUrl}/auth/register`, payload).pipe(
      tap((res) => this.setUserToken(res.accessToken)),
    );
  }

  acceptInvite(token: string, password: string): Observable<AuthTokenResponse> {
    return this.http.post<AuthTokenResponse>(`${this.baseUrl}/auth/accept-invite`, { token, password }).pipe(
      tap((res) => this.setUserToken(res.accessToken)),
    );
  }

  setInstitutionToken(token: string): void {
    this.institutionToken = token;
    if (token) {
      localStorage.setItem(this.institutionTokenStorageKey, token);
    } else {
      localStorage.removeItem(this.institutionTokenStorageKey);
    }
  }

  setInstitutionId(institutionId: string): void {
    this.institutionId = institutionId;
    if (institutionId) {
      localStorage.setItem(this.institutionIdStorageKey, institutionId);
    } else {
      localStorage.removeItem(this.institutionIdStorageKey);
    }
  }

  setUserToken(token: string): void {
    this.userToken = token;
    if (token) {
      localStorage.setItem(this.userTokenStorageKey, token);
    } else {
      localStorage.removeItem(this.userTokenStorageKey);
    }
  }

  clearTokens(): void {
    this.setInstitutionToken('');
    this.setUserToken('');
  }

  getInstitutionToken(): string {
    return this.institutionToken;
  }

  getInstitutionId(): string {
    return this.institutionId;
  }

  getUserToken(): string {
    return this.userToken;
  }

  createInstitution(name: string): Observable<Institution> {
    return this.http
      .post<Institution>(`${this.baseUrl}/institutions`, { name }, { observe: 'response', headers: this.institutionHeaders() })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  createInstitutionUser(payload: { institutionId: string; name: string; email: string; role: string }): Observable<InstitutionUserCreated> {
    return this.http
      .post<InstitutionUserCreated>(`${this.baseUrl}/institution-users`, payload, { observe: 'response', headers: this.institutionHeaders() })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  createProperty(payload: {
    institutionId: string;
    address: string;
    loanAmount: number;
    currentBalance: number;
    monthlyPayment: number;
    dynamicBillingEnabled: boolean;
  }): Observable<Property> {
    return this.http
      .post<Property>(`${this.baseUrl}/properties`, payload, { observe: 'response', headers: this.institutionHeaders() })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  attachAgreement(
    propertyId: string,
    payload: { noticeDays: number; valuationMethod: string; partialClaimMethod: string },
  ): Observable<PropertyAgreement> {
    return this.http
      .post<PropertyAgreement>(`${this.baseUrl}/properties/${propertyId}/agreement`, payload, {
        observe: 'response',
        headers: this.institutionHeaders(),
      })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  inviteOwner(
    propertyId: string,
    payload: { name: string; email: string; maxOwnershipPercent: number | null },
  ): Observable<Acknowledgement> {
    return this.http
      .post<Acknowledgement>(`${this.baseUrl}/properties/${propertyId}/owners`, payload, {
        observe: 'response',
        headers: this.institutionHeaders(),
      })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  acknowledge(propertyId: string): Observable<Acknowledgement> {
    return this.http
      .post<Acknowledgement>(`${this.baseUrl}/properties/${propertyId}/acknowledge`, {}, {
        observe: 'response',
        headers: this.userHeaders(),
      })
      .pipe(map((res) => this.applyRefreshedToken(res, 'user')));
  }

  getProperty(propertyId: string): Observable<PropertyDetailResponse> {
    return this.http
      .get<PropertyDetailResponse>(`${this.baseUrl}/properties/${propertyId}`, {
        observe: 'response',
        headers: this.institutionHeaders(),
      })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  getOwners(propertyId: string): Observable<PropertyOwnersResponse> {
    return this.http
      .get<PropertyOwnersResponse>(`${this.baseUrl}/properties/${propertyId}/owners`, {
        observe: 'response',
        headers: this.institutionHeaders(),
      })
      .pipe(map((res) => this.applyRefreshedToken(res, 'institution')));
  }

  /** Marketplace view; any signed-in buyer or officer may read it, so send whichever token is present. */
  getListings(limit: number, offset: number): Observable<Listing[]> {
    const token = this.userToken || this.institutionToken;
    return this.http.get<Listing[]>(`${this.baseUrl}/listings`, {
      params: new HttpParams().set('limit', limit).set('offset', offset),
      headers: new HttpHeaders({ Authorization: `Bearer ${token}` }),
    });
  }

  private institutionHeaders(): HttpHeaders {
    return new HttpHeaders({ Authorization: `Bearer ${this.institutionToken}` });
  }

  private userHeaders(): HttpHeaders {
    return new HttpHeaders({ Authorization: `Bearer ${this.userToken}` });
  }

  private applyRefreshedToken<T>(response: HttpResponse<T>, tokenType: 'institution' | 'user'): T {
    const refreshed = response.headers.get('X-Refreshed-Token');
    if (refreshed) {
      if (tokenType === 'institution') {
        this.setInstitutionToken(refreshed);
      } else {
        this.setUserToken(refreshed);
      }
    }
    return response.body as T;
  }

  private extractInstitutionId(token: string): string {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return '';
    }
    const payload = JSON.parse(this.base64UrlDecode(parts[1]));
    return typeof payload.institutionId === 'string' ? payload.institutionId : '';
  }

  private base64UrlDecode(value: string): string {
    const base64 = value.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(value.length / 4) * 4, '=');
    return atob(base64);
  }
}
