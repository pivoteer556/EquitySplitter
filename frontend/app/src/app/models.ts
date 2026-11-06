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

export interface InstitutionBootstrapResponse {
  accessToken: string;
  tokenType: string;
  institution: Institution;
  institutionUser: InstitutionUser;
}
