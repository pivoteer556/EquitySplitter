# Vertical slice: design for review (2026-11-12)

Status: DESIGN ONLY. Nothing here is built. Written by Balthazar for the product owner to correct before any code.
Decisions taken from the user (2026-11-12): (a) demo sign-in by operator-run seed script that prints one-time
password-setup links; (b) the v1 schema should already hold the purchase terms (verified below: mostly it does NOT,
details in section 1); (c) display the house as "belonging to" the buyers once the loan application is filed and an
Intent to Proceed (ITP) exists, before closing; (d) an SVG house illustration for properties with no photo.

Verified = I read the file at the cited line. Inferred = my reasoning, not checked against running code. I did not run
anything, did not touch any database, and did not read the live Azure schema (migrations are the evidence for "in the
live DB", assuming 0001 to 0012 were applied there, which is UNVERIFIED).

## 1. Terms map

Every table below was read in `app/models/*` and traced to `alembic/versions/*`. All v1 tables are created in
`0001_initial.py`; the live DB has them if migration 0001 ran (the migrations header in
`docs/specs/updated_mortgage_schema.html:1-12` says the HTML is synced with 0001-0012).

| Term | Where it lives | Evidence | In a migration? | Verdict |
|---|---|---|---|---|
| Purchase price | NOWHERE. `PropertyListing.askingPrice` is the seller's ask, and `EquityTransfer.askingPrice` is a later share sale | `property_listing.py:41`, `equity_transfer.py:19` | listing: `0009_property_listings.py:33`; transfer: `0001_initial.py:185` | **MISSING** |
| Down payment per owner | NOWHERE. `EquityLedger` could carry an opening position, but `cycleId` is NOT NULL (`equity_ledger.py:18-20`), so it cannot exist without a `PaymentCycle` | `equity_ledger.py:15-23` | n/a | **MISSING** |
| Ownership percent per owner | Deliberately DERIVED, not stored: equity balance divided by total equity (`shared_mortgage_feature1_spec.docx`, decision "Share percent"). The input exists (`EquityLedger.runningBalance`, `equity_ledger.py:23`) but nothing ever writes a ledger row (grep of `app/` and `scripts/`: no `EquityLedger(` outside models). `UserProperty.maxOwnershipPercent` is a nullable CAP, not the actual share | `user_property.py:21`; `equity_ledger.py:23` | `0001_initial.py:100`; `:170` | **PARTLY MODELED**: structure present, no data and no reader |
| Loan amount | `Loan.loanAmount` (read source) and the legacy duplicate `Property.loanAmount` | `loan.py:21`, `property.py:18` | `0006_loans.py:32`, `0001_initial.py:64` | **MODELED** |
| Current balance | `Loan.currentBalance` (and legacy `Property.currentBalance`) | `loan.py:22`, `property.py:19` | `0006_loans.py:33` | **MODELED** |
| Interest rate | NOWHERE as a rate. `PaymentCycle.interestDue` is a per-cycle dollar amount | `payment_cycle.py:20` | `0001_initial.py:133` | **MISSING** |
| Loan term | NOWHERE | n/a | n/a | **MISSING** |
| Monthly payment (whole house) | `Loan.monthlyPayment` (and legacy `Property.monthlyPayment`) | `loan.py:23`, `property.py:20` | `0006_loans.py:34` | **MODELED** |
| Each owner's share of the monthly payment | `PaymentCycle` is per owner (`userPropertyId`) with `equityDue`, `interestDue`, `insuranceDue`, `hoaDue`, `otherDue`, `dueDate`, `status`. No code creates cycles (grep: no `PaymentCycle(` outside models) and there is no endpoint | `payment_cycle.py:15-24` | `0001_initial.py:131-137` | **PARTLY MODELED**: table exists and is per owner (the earlier claim "no per-owner dues" is wrong); no writer, no reader. Spec: no cycles on an inactive property |
| Closing date | NOWHERE. `PropertyAgreement.effectiveAt` is when the agreement became effective (set when the last owner acknowledges, `equity_splitter.py:268-271`), not a closing | `property_agreement.py:21` | `0001_initial.py:84` | **MISSING** |
| Shared-equity terms: notice days, valuation method, partial-claim method, effective date | `PropertyAgreement.noticeDays`, `.valuationMethod`, `.partialClaimMethod`, `.effectiveAt` (one row per property, immutable once `effectiveAt` is set by a DB trigger) | `property_agreement.py:18-21` | `0001_initial.py:81-84`; trigger `0002_auth_and_invariants.py:64-80` | **MODELED**, exposed by `GET /properties/{id}` (`equity_splitter.py:319-331`) |
| Dynamic billing flag | `Loan.dynamicBillingEnabled` (legacy copy on Property) | `loan.py:24` | `0006_loans.py:35` | **MODELED** |
| Owner link and sign-off | `UserProperty` (`user_property.py:14-24`) and `OwnerAcknowledgement.signedAt` (`owner_acknowledgement.py:22`); signed rows are immutable by trigger | | `0001_initial.py:88-121`, trigger `0002:86-102` | **MODELED**, endpoints exist (invite, acknowledge, owners) |
| Payments | `Payment.amountPaid`, `.paidAt` | `payment.py:18-19` | `0001_initial.py:149-150` | **MODELED, unused** (no writer, no endpoint) |
| Equity ledger and equity math | `EquityLedger.baseEquityDelta`, `.bonusEquityDelta`, `.runningBalance`; `calculate_equity_deltas`, `next_running_balance` | `equity_ledger.py:21-23`; `app/services/equity.py:4-17` | `0001_initial.py:168-171` | **MODELED, unused**: `equity.py` is imported only by `tests/test_equity_service.py` (grep) |
| Equity transfers and claims | `EquityTransfer` (`status`, `askingPrice`, `sharePercent`, `noticeGivenAt`, `transferredAt`), `TransferClaim` (`claimedPercent`, `claimedAt`) | `equity_transfer.py:18-22`; `transfer_claim.py:21-22` | `0001_initial.py:184-207` | **MODELED, unused** |
| House facts: address, bedrooms, bathrooms, square feet, description, listed date | `Property.address`; `PropertyListing.bedrooms/bathrooms/squareFeet/description/listedAt` | `property.py:17`; `property_listing.py:42-46` | `0001_initial.py:63`; `0009:34-38` | **MODELED**. Buyers have NO read endpoint for `PropertyListing` (only officer routes, `property_listings.py:24-41`); `GET /listings` returns Property id, address, status and date only (`equity_splitter.py:302-316`) |
| Application filed; ITP | NOWHERE. `ConnectionRequest.status` (`pending/accepted/declined/cancelled`, `connection_request.py:12`) is a buyer asking a professional about a property, not a loan application | | | **MISSING** |

Correction of the earlier "not modeled" list (purchase price, per-owner down payment, actual ownership percent,
interest rate, loan term, closing date, per-owner monthly split):

- Correct as stated: purchase price, per-owner down payment, interest rate, loan term, closing date. Five columns'
  worth of data the user may have remembered as "v1" but that v1 never had.
- Partly wrong: ownership percent and per-owner monthly split. v1 DID design the structures (the ledger and per-owner
  `PaymentCycle`) and chose to derive percent rather than store it. What is missing is a writer and a reader, and an
  opening position (the ledger cannot hold a down payment without a cycle).
- Wrong if read as "nothing": the shared-equity terms, loan amount, balance, whole-house monthly payment, owner links
  and acknowledgements are modeled and (for the loan and agreement) already served.

Honest summary: v1 is the post-closing machine (cycles, payments, ledger, transfers). It has no model of the purchase
itself. The slice needs a small purchase-side addition. The ledger path stays for after closing.

## 2. Purchase-process states

### Existing vocabularies (verified)

- `Property.status`: free text, default `pending_acknowledgement` (`property.py:22`); set to `active` when every
  invited owner has acknowledged (`equity_splitter.py:266-271`). Not a constant anywhere; `/listings` filters on the
  literal (`equity_splitter.py:304`) and connection requests require it (`connection_requests.py:32`).
- `PropertyListing.status`: `draft, listed, withdrawn, sold` (`property_listing.py:11`). `sold` has no allowed
  transition target (`:15-20`; route answers 409 "Not available yet").
- `OwnerAcknowledgement.signedAt` null or set (`owner_acknowledgement.py:22`). `UserProperty` = access link
  (`ensure_user_property_scope`, used by `load_property`, `app/api/deps/properties.py:15-31`).
- `ConnectionRequest`: buyer to professional about a pending property. Not used by the slice.

### Stages for the slice

One derived stage, computed in ONE function (`purchase_stage(property, purchase)` in a new
`app/services/purchase.py`), never stored: no second source of truth (Smells.md, "Null as a hidden mode").

| Stage | Condition | Existing data it maps to | Owner sees |
|---|---|---|---|
| `listed` | no purchase row, or no `applicationFiledAt` | `PropertyListing.status = listed`; `Property.status = pending_acknowledgement` | Nothing on home (no link yet), or "Applicant" if linked |
| `application_filed` | `applicationFiledAt` set | new column | House, "Application filed on <date>". NOT shown as owned |
| `intent_to_proceed` | `intentToProceedAt` set | new column | "Belongs to" display: house, owners and shares, terms, "Intent to proceed on <date>; closing planned <date>" |
| `closed` | `closedAt` set | new column | Same, "Closed on <date>" (display only in the slice) |

"Buyers displayed as owners" is the display consequence of `intent_to_proceed` plus `closed`, not a separate stored
state. "Belongs to" is a data statement, not legal title; the page says so in one sentence ("Shown as the buyers of this
home in EquitySplitter's records. This is not a record of legal title.").

Orthogonal flag, already existing: the shared-equity agreement acknowledged (`Property.status = active`). I keep it
out of the stage because the owner acknowledge screen is itself a backlog gap. Open question for later: today
`active` also means "payments may begin" (spec: no cycles on an inactive property); with a `closed` stage, payments
should require BOTH. Not needed for the slice.

### Reconciling the deferral table

The backlog proposes deferring "ITP and rate lock" (2h). Reconciled: in scope is ONE timestamp
(`intentToProceedAt`) and one for the application (`applicationFiledAt`), written by the seed script only. Deferred
and untouched: underwriting stages, rate lock, any officer UI to set them, listing `sold` transition, ability to repay,
`ConnectionRequest` acceptance. A future origination pipeline replaces these two timestamps with real events; nothing
here blocks that.

### Minimum additions (migration `0013_purchase_terms`, down_revision `0012_recovery_codes`)

```python
# new small table: the purchase itself (one row per property)
op.create_table(
    "propertyPurchases",
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("propertyId", postgresql.UUID(as_uuid=True),
              sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, unique=True),
    sa.Column("purchasePrice", sa.Numeric(12, 2), nullable=False),
    sa.Column("closingDate", sa.Date(), nullable=True),                      # planned, then actual
    sa.Column("applicationFiledAt", sa.DateTime(timezone=True), nullable=True),
    sa.Column("intentToProceedAt", sa.DateTime(timezone=True), nullable=True),
    sa.Column("closedAt", sa.DateTime(timezone=True), nullable=True),
    sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.CheckConstraint("purchasePrice > 0", name="ck_propertyPurchases_price"),
    # a stage cannot be set without the one before it (ITP needs an application, closed needs ITP)
    sa.CheckConstraint("\"intentToProceedAt\" IS NULL OR \"applicationFiledAt\" IS NOT NULL", name="ck_propertyPurchases_itp_needs_application"),
    sa.CheckConstraint("\"closedAt\" IS NULL OR \"intentToProceedAt\" IS NOT NULL", name="ck_propertyPurchases_closed_needs_itp"),
)
# loan terms belong on the loan (loans table, 0006)
op.add_column("loans", sa.Column("interestRatePercent", sa.Numeric(6, 3), nullable=True))   # 6.250
op.add_column("loans", sa.Column("termMonths", sa.Integer(), nullable=True))                 # 360
# each owner's contribution at purchase (a contract term, known before closing)
op.add_column("userProperties", sa.Column("downPaymentAmount", sa.Numeric(12, 2), nullable=True))
```

New columns are nullable because existing rows (the live DB) have no values. Why these homes:

- `loans`: the rate and term are loan terms and `Loan` is already the loan source of truth (`equity_splitter.py:122-133`);
  the legacy `Property` columns are transitional and must not grow.
- `userProperties.downPaymentAmount`: the down payment is a contract term (the spec says share percent is "a financial
  outcome, not a contract term"). Ownership percent is then DISPLAYED as each owner's share of total down payments
  (initial equity share), computed in the one service function, never stored. After closing the ledger takes over
  (section 6, cut line). The ledger route needs a `PaymentCycle` per opening row, which would mean seeding a fake
  "cycle 0" to hold a down payment: I reject it for the slice (labelled: a risk I am NOT taking).
- Monthly share per owner: DERIVED for display (`monthlyPayment * share`, rounded to cents, remainder to the largest
  owner), labelled "estimated split". No `PaymentCycle` rows (spec rules them out before activation).
- No interest or amortization calculation anywhere (user decision on the backlog default: stored values for display).

Migration is additive only; the down migration drops the table and the three columns. Test with the existing SQLite
test DB (the CHECK constraints work there) and `tests/test_alembic_env.py` style upgrade check. Docs in the same commit
(CLAUDE.md rule): `docs/specs/updated_mortgage_schema.html` (header list, ER blocks), a dated amendment in the Feature 1
spec change log (.docx), `docs/specs/README.md` row, and BACKLOG.md.

## 3. Seed data

All fictional. Street and city are invented and NOT checked against any map (inferred safe; "Willowmere Heights" and
"Larkspur Court" are not intended to be real; the ZIP `00000` is invalid on purpose).

### The house

| Field | Value |
|---|---|
| `Property.address` | `418 Larkspur Court, Willowmere Heights, OH 00000` |
| `PropertyListing.status` | `listed`, `listedAt` 2026-09-15 |
| `askingPrice` | 489,000.00 |
| `bedrooms`, `bathrooms`, `squareFeet` | 4, 2.5, 2,140 |
| `PropertyPurchases.purchasePrice` | 485,000.00 |
| `closingDate` | 2026-12-18 |
| `applicationFiledAt` / `intentToProceedAt` | 2026-10-20 / 2026-11-05 |

Description (AI-written, fictional; fits the 5000-char cap at `schemas/property_listing.py`):

> Set at the quiet end of Larkspur Court, this four-bedroom home pairs a bright, open main floor with the kind of yard
> that gets used. The kitchen opens to a sunny dining area and a family room with a gas fireplace, so the cook is
> never cut off from the conversation. Upstairs, the primary suite has a walk-in closet and a double-sink bath; three
> more bedrooms share a second full bath. A two-car garage, a covered front porch and a fenced backyard with a
> small patio round it out. Sidewalks, a neighborhood park and the elementary school are a short walk away. Built in
> 2004 and kept up since: new roof in 2022, updated HVAC in 2024.
> (Sample listing for demonstration; not a real property.)

### Accounts (example.com is a reserved domain; all names invented)

| Person | Email | Down payment | Share of down payments | Estimated monthly share |
|---|---|---|---|---|
| Marisol Vega | `marisol.vega@example.com` | 80,000.00 | 50.00% | 1,000.54 |
| Dev Raman | `dev.raman@example.com` | 50,000.00 | 31.25% | 625.34 |
| Hana Lindqvist | `hana.lindqvist@example.com` | 30,000.00 | 18.75% | 375.20 |

Totals: down payments 160,000.00; loan 325,000.00 (= 485,000.00 - 160,000.00, checked); rate 6.250% fixed, 360 months;
principal-and-interest payment 2,001.08 per month (computed with the standard annuity formula; shares sum to 2,001.08).
Taxes and insurance excluded and the page says so. `maxOwnershipPercent` stays null (uncapped); do not reuse the cap
as the share.

Rows the foreign keys force (verified): `institutions` row (`Property.institutionId` NOT NULL, `property.py:14-16`):
name `Willowmere Demo Lending (fictional)`. An officer row is NOT required by any FK for the slice
(`institutionUsers` is referenced only by `ConnectionRequest`, unused here), so I recommend NO demo officer: an officer
cannot sign in without the 2FA enrolment (`auth.py:194-198`) and would add an unneeded credential. Agreement:
`noticeDays` 60, `valuationMethod` and `partialClaimMethod` from the vocabulary the officer endpoint accepts (check
values in the agreement schema before the seed is written; I did not verify the allowed strings), `effectiveAt` null,
acknowledgements unsigned (so owners can acknowledge on their own screen later).

### `scripts/seed_demo.py` (design)

```
python -m scripts.seed_demo [--stage application|itp] [--base-url https://equitysplitter.app]
```

- Same shape as `scripts/create_platform_admin.py`: `main(argv, db_factory)` so a test passes the SQLite session factory
  (pattern: `tests/test_create_platform_admin_script.py`).
- Idempotent by natural keys: institution by name, property by address and institution, user by normalized email
  (`normalize_email`, `app/schemas/types.py`), `UserProperty` by the unique (userId, propertyId), listing by
  propertyId and `status = listed`, purchase by `propertyId` unique. Re-run changes nothing except: `--stage`
  advances the purchase timestamps (set-if-null; never rewound) and the links are re-printed.
- Created users get `passwordHash=unusable_password_hash()` exactly as `invite_owner` does (`equity_splitter.py:213`).
- Links: call `issue_invite_token(db, user.id)` (`app/services/auth.py:108`, 7 days, `INVITE_TOKEN_DAYS` at `:21`) and
  print `<base-url>/accept-invite#token=<token>`, the same line format as `create_platform_admin.py`. Only for users
  whose `passwordSetAt` is None (same rule as `_with_invite_token`, `equity_splitter.py:177-182`); for a user who has
  already chosen a password the script prints "already set up" and no link. It takes no password argument and prints
  none (a test mirrors `test_script_takes_and_prints_no_password`).
- DB triggers: `propertyAgreements` rows are immutable once `effectiveAt` is set and signed `ownerAcknowledgements`
  are immutable (`0002_auth_and_invariants.py:64-102`). The seed therefore INSERTS the agreement once, unsigned, and
  never updates it. It cannot rewind to an earlier state after owners sign. Stated up front in `--help`.
- The seed does NOT go through HTTP routes (no officer token to hold; the officer 2FA makes that impractical), so it
  must write the same rows the routes would: agreement, `UserProperty`, `OwnerAcknowledgement(signedAt=None)`. Risk:
  drift from the routes. Mitigation: a test that seeds, then GETs `/properties/{id}` and `/owners` as a seeded buyer.

Who runs it: the user. Against the live Azure Postgres it writes real rows; I will not run it. Safe order: (1) run the
tests; (2) run it against the local Docker Postgres used by e2e (`es-pg`, per project memory; set `DATABASE_URL` to the
local one) or a throwaway SQLite file; (3) review the printed output; (4) the user sets `DATABASE_URL` to the Azure
instance and runs it once, then opens each link and chooses the password for that account.

Honesty about principle 2c-1 for a demo: these are three fictional people, so "the account holder" is whoever opens the
link (the user). The user will know those three passwords and anyone else who is to sign in as a co-buyer needs the user
to give them access. That is the cost of decision (a); the read-only "view as" mode (backlog option 3) stays deferred.
Single-use: a second visit of a used link is refused (`accept_invite`, `app/services/auth.py:203-217`).

Owner 2FA (backlog 2l): NOT a blocker. Verified: `POST /auth/login` challenges only `InstitutionUser`; a `User` gets a
`LoginResponse` straight from the password (`app/api/routes/auth.py:182-201`, `isinstance(account, InstitutionUser)`
branches only). 2FA for owners is not built. When it is, the three demo accounts would each need an authenticator
enrolment by whoever holds them; the seed needs no change. Flag it in the 2l item when that work starts.

## 4. SVG house illustration

- File: inline Angular component, `frontend/app/src/app/house-illustration.component.ts` (selector
  `app-house-illustration`), template is the SVG in Appendix A. Why inline and not `public/house.svg` used by `<img>`:
  an SVG loaded as an image cannot read the page's CSS custom properties, so it cannot follow the brand tokens. Inline
  markup can. The component also needs no HTTP fetch (the Static Web App `staticwebapp.config.json` stays untouched).
  The logo already works this way (`svg.logo` in `app.html`, per project memory), so it is the established pattern.
- Used as the picture whenever a property has no photo (no photo storage exists: backlog 2h step 5 is deferred, so that
  is always, today). Three places: owner home (large), listing card on `/listings` (small, `aria-hidden`), and the
  future listing detail. The component takes `@Input() label` (default empty).
- Accessibility: it is an illustration, not data. Next to the address text it is `aria-hidden="true"` with no role
  (screen readers get the address, not "a house"). Where it is the only visual (no adjacent address) pass `label` and
  it renders `role="img"` with `aria-label`. The SVG carries `<title>` only in the labelled mode. It states that the
  picture is a placeholder illustration, not the actual home, in the visible caption on the home page ("Illustration").
- Theming: the app currently has ONE theme; `styles.css:3` says "no dark-mode media variant yet". So tokens, not a
  media query. The component reads CSS custom properties with fallbacks (`var(--house-wall, ...)`), and the illustration
  tokens are defined in `styles.css` next to the brand ones, derived from existing values where possible:
  `--house-roof: var(--brand-navy)`, `--house-trim: var(--brand-blue-dark)`, `--house-door: var(--brand-amber)`,
  `--house-wall: #FFFFFF`, `--house-glass: var(--brand-blue)`, plus three new greens (`--house-lawn`, `--house-tree`,
  `--house-tree-dark`) because the brand palette has no green. A future dark theme overrides these seven tokens in one
  place. The sky is NOT drawn (transparent), so it sits on the cream card (`--brand-surface`) in the page or on any
  background. Contrast: decorative, so WCAG 1.4.11 does not require a ratio; the `e2e/contrast.spec.ts` audit (project
  memory) checks text, so an `aria-hidden` SVG adds nothing for it to fail on (inferred; I did not run it).
- Karma spec: renders, is `aria-hidden` by default, has `role="img"` and the label when `label` is set, uses no
  hard-coded colour outside `var(...)` fallbacks.

## 5. Owner "my home" page

- Route `/home`, guarded by `authGuard` today; the guard admits officer tokens too (`auth.guard.ts:4-12`), so the page
  must handle an officer opening it (it lists nothing for them; they have `/workbench`). Cleaner: add an `ownerGuard`
  (user token only) beside `officerGuard`. Recommendation: add `ownerGuard`; 5 lines plus a spec.
- Landing change: owners go to `/home` after sign-in and accept-invite (currently `/listings`, project memory and
  `accept-invite-page.component.ts:35`). If an owner has zero properties, `/home` links to `/listings`. This changes two
  existing specs (login routing, accept-invite) and any e2e that expects `/listings`; counted in the plan.
- Data flow: `GET /properties` for a buyer already returns only linked properties via `_visible_properties`
  (`equity_splitter.py:278-299`). With one property the page goes straight to its detail; with several it lists them.
  Then `GET /properties/{id}` and `GET /properties/{id}/owners`, both behind `load_property`
  (404 missing or malformed, 403 not enrolled).

What it shows: house card (illustration, address, bedrooms, bathrooms, square feet, description); the stage statement
(section 2); owners with name, down payment, share and estimated monthly share, and "agreement signed / not yet";
terms table (purchase price, down payments total, loan amount, rate, term, monthly payment, closing date); agreement
terms in plain language (notice days, valuation method, partial-claim method, effective date or "not yet effective").

### API additions that are truly needed (minimum, all additive)

The existing endpoints cannot serve it because a buyer has no read route for the listing fields or for the purchase
terms. I propose EXTENDING the two existing GETs rather than adding routes:

`GET /properties/{id}` today returns `{property, agreement}` (`equity_splitter.py:319-331`, `PropertyDetailRead`).
Add `purchase` and `listing`, both nullable:

```json
{
  "property": {"...existing PropertyRead..."},
  "agreement": {"...existing, or null..."},
  "purchase": {
    "stage": "intent_to_proceed",
    "purchasePrice": "485000.00",
    "closingDate": "2026-12-18",
    "applicationFiledAt": "2026-10-20T00:00:00Z",
    "intentToProceedAt": "2026-11-05T00:00:00Z",
    "closedAt": null,
    "interestRatePercent": "6.250",
    "termMonths": 360
  },
  "listing": {"bedrooms": 4, "bathrooms": "2.5", "squareFeet": 2140, "description": "..."}
}
```

`GET /properties/{id}/owners` today returns name, email, `maxOwnershipPercent`, `signedAt`
(`PropertyOwnerStatus`, `owner_acknowledgement.py`). Add `downPaymentAmount`, `sharePercent`, `estimatedMonthlyShare`
(derived by the service function, not stored).

Observed, not changed: `/owners` returns every owner's EMAIL to any linked buyer (`equity_splitter.py:374-413`). Co-buyers
seeing each other's address may be acceptable; it is a privacy decision I am flagging, not making (question 4).
Staying minimal, I do not add a `GET /listings/{id}` for buyers, any write endpoint, or a "set stage" route: the
seed script sets the stage.

Money is serialized as strings or numbers consistent with the existing `Decimal` read schemas (`PropertyRead`); keep
whatever the existing frontend `Property` type does (I did not check how `models.ts` types money; it is a one-line
decision for whoever builds it).

DEVIATION (2026-11-12, as built): S2 built `purchase` as always-an-object, with stage `listed` and every other field null
when there is no purchase row, where this section made it nullable. S4 gave the `app-house-illustration` `label` input a
default (`Illustration of a suburban house`) where the design had it empty. Both are recorded in `docs/specs/README.md`.

## 6. Slice plan

Standard: minimum verifiable change = one observable behavior, test first, one commit; docs and BACKLOG.md in the same
commit (CLAUDE.md). Sizes: S under about 1 hour, M a few hours, L a day. E2E is Playwright against the real backend and
throwaway DB `equity_e2e` (`frontend/app/e2e/`).

| # | Change (observable behavior) | Test first | E2E? | Size | Depends |
|---|---|---|---|---|---|
| 1 | Migration 0013 + models + `purchase_stage()`: a purchase row, loan rate and term, and `downPaymentAmount` persist; stage derivation table; CHECK constraints reject ITP without application | pytest: model round-trip, stage table, constraint failures; upgrade/downgrade | no | M | none |
| 2 | `GET /properties/{id}` returns `purchase` and `listing`; `/owners` returns down payment, share, estimated monthly share; unlinked buyer 403, missing 404 | pytest in `tests/` (reuse the property lookup rule tests as a template) | no | M | 1 |
| 3 | `scripts/seed_demo.py`: seeds house, 3 buyers, prints 3 one-time links, no password; re-run is idempotent and re-issues links only for unset accounts; link sets password then sign-in works, buyer can GET their property | pytest with `db_factory` like `test_create_platform_admin_script.py`; plus a seed-then-API test | yes, optional: run the seed in `global-setup.ts` against `equity_e2e`, sign in from a printed link | M | 1, 2 |
| 4 | `app-house-illustration` component | Karma spec (section 4) | no | S | none (can run in parallel with 1 to 3) |
| 5 | `/home` page for an owner: card, owners and shares, terms table | Karma with stubbed API | yes, after 3 | M | 2, 4 |
| 6 | Stage statement and "belongs to" wording by stage | Karma, one case per stage | extend 5's e2e with `--stage application` vs `itp` | S | 5 |
| 7 | Owners land on `/home` after login and accept-invite; `ownerGuard` | update existing Karma specs and e2e expectations | yes (existing sign-in e2e) | S | 5 |
| 8 | Illustration on the `/listings` card | Karma | no | S | 4 |
| 9 | Owner acknowledge screen (existing gap): the signed owner sees "signed"; the last signature makes the property `active` | Karma plus e2e (this is the one flow that exercises triggers end to end) | yes | M | 5 |
| 10 | Docs sync (spec amendments, schema HTML, README rows) | n/a, folded into each commit above | n/a | folded | all |

Cut line if time is short: ship 1, 2, 3, 4, 5, 6 (the slice is visible and demoable); defer 7 (a link from
`/listings` works meanwhile), 8 and 9. `closed` stage is display-only and the seed does not write it.

Risks and unknowns (honest):
- Allowed values for `valuationMethod` and `partialClaimMethod` not verified; check the agreement schema first.
- Live DB state: whether migrations 0001-0012 are applied on Azure is unverified; ~~the user runs `alembic upgrade` (and
  the seed) and must be asked before anything touching Azure.~~ CORRECTED 2026-11-12: migrations are applied automatically at container start by the deploy (`alembic upgrade head` in `scripts/entrypoint.sh`), so 0001-0012 were applied by earlier deploys (unverified directly) and 0013 is applied by the deploy of a89b5f9. Only the SEED (it writes rows into the live DB) is run by the user, who must give his go first.
- The seed writes rows by hand rather than through routes; drift risk, mitigated by the seed-then-API test.
- Editing the .docx spec amendment is fiddly (the repo mandates it); budget it, do not skip it.
- E2E for the home page needs the seed in `global-setup.ts`; unverified that the setup can import the Python script
  (it already shells out to `reset-db.py`, `e2e/reset-db.py`).
- Removing the `/listings` landing for owners changes existing tests; counted in item 7.

## 7. Questions that remain for the user

1. Store the down payment as `userProperties.downPaymentAmount` (my default, section 2) or seed a "closing cycle" and
   hold it in the equity ledger? Default: the column; the ledger takes over at closing.
2. Who sees the "belongs to" display? Default: only the owners themselves and officers of the institution; the public
   `/listings` card shows no names (at most "Under contract").
3. Is the `closed` stage in the slice or display-only? Default: display-only; the seed never sets `closedAt`.
4. `/owners` already shows every owner's email to each linked buyer. Keep, or restrict to names for buyers? Default:
   leave the existing endpoint alone this slice and show names only on the new page (still sourced from `/owners`, so
   the email stays in the payload: restricting it is a separate small change I recommend queuing).
5. Owners landing on `/home` instead of `/listings` after sign-in: OK? Default: yes, with `/listings` one click away.

## Appendix A: SVG draft (viewBox 400 by 260, transparent sky)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 260" aria-hidden="true" focusable="false">
  <!-- ground and walk -->
  <rect x="0" y="205" width="400" height="55" fill="var(--house-lawn, #6B9A5B)"/>
  <rect x="188" y="205" width="24" height="55" fill="var(--house-path, #E9E4D4)"/>
  <polygon points="300,205 352,205 372,260 292,260" fill="var(--house-path, #E9E4D4)"/>
  <!-- tree -->
  <rect x="42" y="150" width="9" height="58" fill="var(--house-trunk, #6B4F3A)"/>
  <circle cx="46" cy="132" r="34" fill="var(--house-tree, #4F7F4A)"/>
  <circle cx="60" cy="146" r="22" fill="var(--house-tree-dark, #3F6B3C)"/>
  <!-- garage -->
  <rect x="290" y="150" width="86" height="55" fill="var(--house-wall, #FFFFFF)" stroke="var(--house-trim, #2A4688)" stroke-width="2"/>
  <polygon points="282,153 333,128 384,153" fill="var(--house-roof, #14213D)"/>
  <rect x="302" y="168" width="62" height="37" fill="var(--house-trim, #2A4688)"/>
  <path d="M302 177H364M302 186H364M302 195H364" stroke="var(--house-wall, #FFFFFF)" stroke-width="1.5" opacity="0.6"/>
  <!-- main house -->
  <rect x="236" y="62" width="16" height="34" fill="var(--house-trim, #2A4688)"/>
  <rect x="110" y="118" width="180" height="87" fill="var(--house-wall, #FFFFFF)" stroke="var(--house-trim, #2A4688)" stroke-width="2"/>
  <polygon points="98,123 200,56 302,123" fill="var(--house-roof, #14213D)"/>
  <circle cx="200" cy="96" r="10" fill="var(--house-glass, #3A5FB0)" stroke="var(--house-wall, #FFFFFF)" stroke-width="3"/>
  <!-- windows -->
  <g fill="var(--house-glass, #3A5FB0)" stroke="var(--house-wall, #FFFFFF)" stroke-width="3">
    <rect x="126" y="142" width="34" height="32"/>
    <rect x="240" y="142" width="34" height="32"/>
  </g>
  <path d="M143 142V174M126 158H160M257 142V174M240 158H274" stroke="var(--house-wall, #FFFFFF)" stroke-width="2"/>
  <!-- porch and door -->
  <rect x="176" y="150" width="48" height="6" fill="var(--house-trim, #2A4688)"/>
  <rect x="186" y="156" width="28" height="49" fill="var(--house-door, #E0A800)"/>
  <circle cx="208" cy="182" r="2" fill="var(--house-roof, #14213D)"/>
  <rect x="172" y="198" width="56" height="7" fill="var(--house-trim, #2A4688)"/>
</svg>
```

Draft only: coordinates not rendered or visually checked by me (no renderer was run). The builder should open it in a
browser and adjust before the component spec is written.

## Done

File: `c:\Users\Alexa\source\EquitySplitter\docs\design\vertical-slice.md`.

1. The earlier "not modeled" list is half right: purchase price, per-owner down payment, interest rate, loan term and
   closing date are truly MISSING (no column anywhere; `askingPrice` is the ask, `interestDue` is dollars, `effectiveAt`
   is agreement effect).
2. Ownership percent and per-owner monthly split are PARTLY modeled in v1: percent is deliberately derived from
   `EquityLedger.runningBalance`; per-owner dues exist in `PaymentCycle` (`userPropertyId`). Both are unused: no code
   writes ledger, cycle, payment or transfer rows, and `equity.py` is only called by its test.
3. Loan amount, balance, whole-house monthly payment, agreement terms, owner links and acknowledgements are modeled,
   in migrations 0001/0006, and (loan, agreement) served by `GET /properties/{id}`.
4. Buyers have no read route for `PropertyListing` fields (officer-only) and `/listings` shows id, address, status, date.
5. Proposal: migration 0013: `propertyPurchases` (price, closing date, application, ITP, closed timestamps),
   `loans.interestRatePercent/termMonths`, `userProperties.downPaymentAmount`. Stage derived in one function, never stored.
6. ITP reconciled: only two timestamps, set by the seed; rate lock, underwriting and officer UI stay deferred.
7. Seed: fictional 418 Larkspur Court house, 3 `example.com` buyers (50/31.25/18.75% of 160k down), loan 325k at 6.25%
   for 360 months = 2,001.08 per month; links from `issue_invite_token`; no demo officer needed.
8. Owner 2FA is not a blocker: user login never challenges (`auth.py:182-201`).
9. Page `/home` by extending two existing GETs additively; no new route and no write endpoints.
10. Slice plan is 10 ordered commits (items 1 to 6 are the demoable core); five questions with defaults.

## Not done

- No code, tests, migrations, schema docs, spec .docx, BACKLOG.md or other file changed; nothing committed or staged;
  the untracked `.pbids` untouched.
- Nothing run: no pytest, no seed, no database access, no Azure, GitHub or Terraform.
- Did not render or visually check the SVG; did not run the contrast e2e.
- Did not verify the allowed `valuationMethod`/`partialClaimMethod` strings, how `models.ts` types money, or that
  migrations 0001-0012 are applied on the live DB.
- Did not read the Feature 2 spec .docx; Feature 1 text was extracted and skimmed for the relevant decisions only.

## Dilemmas

None. One judgment call for Casper to record: I chose NOT to model the down payment through the equity ledger even
though it is the "v1 way", because the ledger requires a `PaymentCycle` per row and the spec forbids cycles before
activation (question 1).

## Memory update

- 2026-11-12: Design for the vertical slice is `docs/design/vertical-slice.md` (design only). v1 has NO purchase price, down payment, interest rate, loan term or closing date; ownership percent is derived from `EquityLedger.runningBalance` and per-owner dues live in `PaymentCycle`, but no code writes ledger, cycle, payment or transfer rows. Proposed migration 0013 `propertyPurchases` + `loans.interestRatePercent/termMonths` + `userProperties.downPaymentAmount`.
- 2026-11-12: Seed gotchas: `propertyAgreements` and signed `ownerAcknowledgements` are immutable by DB trigger (0002:64-102), so seed inserts once and never rewinds; user login never challenges 2FA (only `InstitutionUser`, `auth.py:182-201`); no officer row is needed for a Property (only `institutions`).
