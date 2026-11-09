export interface Institution {
  id: string;
  name: string;
  createdAt: string;
}

export interface InstitutionUser {
  id: string;
  institutionId: string;
  name: string;
  email: string;
  role: string;
  createdAt: string;
}

export interface Property {
  id: string;
  institutionId: string;
  address: string;
  loanAmount: number;
  currentBalance: number;
  monthlyPayment: number;
  dynamicBillingEnabled: boolean;
  status: string;
  createdAt: string;
}

export interface PropertyAgreement {
  id: string;
  propertyId: string;
  noticeDays: number;
  valuationMethod: string;
  partialClaimMethod: string;
  effectiveAt: string | null;
}

export interface Acknowledgement {
  id: string;
  agreementId: string;
  userPropertyId: string;
  signedAt: string | null;
  inviteToken?: string | null;
}

export interface PropertyOwnerStatus {
  userPropertyId: string;
  userId: string;
  name: string;
  email: string;
  maxOwnershipPercent: number | null;
  signedAt: string | null;
}

export interface PropertyOwnersResponse {
  owners: PropertyOwnerStatus[];
}

export interface PropertyDetailResponse {
  property: Property;
  agreement: PropertyAgreement | null;
}

export interface AuthTokenResponse {
  accessToken: string;
  tokenType: string;
}

/** Response of POST /auth/login: the token plus what kind of account signed in. */
export interface LoginResponse extends AuthTokenResponse {
  userType: 'user' | 'institution_user';
  isPlatformAdmin: boolean;
  role: string | null;
  institutionId: string | null;
}

/** POST /auth/login answer for an officer with an authenticator: no token yet, only a challenge for POST /auth/login/totp. */
export interface SecondFactorChallenge {
  userType: 'institution_user';
  secondFactorRequired: true;
  challengeToken: string;
}

export interface InstitutionBootstrapResponse {
  institution: Institution;
  institutionUser: InstitutionUser;
  activationToken: string;
  /** Relative link, '/activate#token=...'; prefix it with the site origin to hand it to the officer. */
  activationPath: string;
}

export interface InstitutionUserCreated extends InstitutionUser {
  activationToken: string;
  activationPath: string;
}

export interface Listing {
  id: string;
  address: string;
  status: string;
  createdAt: string;
}
