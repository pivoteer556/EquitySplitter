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
  // The API sends money as decimal strings ("485000.00"); only the create payload takes numbers.
  loanAmount: string;
  currentBalance: string;
  monthlyPayment: string;
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
  /** Null = not set; the two share fields are null unless every owner on the property has a down payment. */
  downPaymentAmount: string | null;
  sharePercent: string | null;
  estimatedMonthlyShare: string | null;
}

export interface PropertyOwnersResponse {
  owners: PropertyOwnerStatus[];
}

/** Always an object; with no purchase row the stage is 'listed' and the rest is null. */
export interface PropertyPurchase {
  stage: string;
  purchasePrice: string | null;
  closingDate: string | null;
  applicationFiledAt: string | null;
  intentToProceedAt: string | null;
  closedAt: string | null;
  interestRatePercent: string | null;
  termMonths: number | null;
}

export interface PropertyListingSummary {
  askingPrice: string;
  bedrooms: number | null;
  bathrooms: string | null;
  squareFeet: number | null;
  description: string | null;
}

export interface PropertyDetailResponse {
  property: Property;
  agreement: PropertyAgreement | null;
  purchase: PropertyPurchase;
  listing: PropertyListingSummary | null;
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

/** POST /auth/login/totp/enroll-confirm answer: a normal login plus the one-time recovery codes, shown once and never retrievable again. */
export interface EnrolConfirmResponse extends LoginResponse {
  recoveryCodes: string[];
}

/** POST /auth/institution/totp/recovery-codes answer: a fresh set of one-time codes (the old set stops working), shown once. */
export interface RecoveryCodesResponse {
  recoveryCodes: string[];
}

/** POST /auth/login answer for an officer with an authenticator: no token yet, only a challenge for POST /auth/login/totp. */
export interface SecondFactorChallenge {
  userType: 'institution_user';
  secondFactorRequired: true;
  challengeToken: string;
}

/** POST /auth/login answer for an officer with no authenticator yet: no token, only a challenge for the enrolment endpoints. */
export interface EnrolmentChallenge {
  userType: 'institution_user';
  enrolmentRequired: true;
  challengeToken: string;
}

/** POST /auth/login/totp/enroll-start answer: the secret to type into an authenticator app, and the same as an otpauth link. */
export interface TotpEnrollment {
  secret: string;
  otpauthUri: string;
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
