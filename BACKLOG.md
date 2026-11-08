# Backlog

Ordered list of work. One item per change, each proven by a check that fails before and passes after.
Update this file in the same commit that finishes an item.

**Items are never deleted.** A finished item is struck through (`~~like this~~`) and annotated with **Done**, the
commit that finished it, and what is still unverified. The backlog doubles as an audit trail of what was asked, what
was done, and how it was checked.

## Direction: HTML-first UI

Prefer native platform features over TypeScript: real `<form>` elements with `required` / `type=email` / `minlength` /
`pattern` and `:user-invalid`, `autocomplete`, `<dialog>`, the Popover API (`popover`) for toasts and menus, `<details>`,
CSS `:has()` / container queries / nesting. Keep Angular bindings and `friendlyError` only where a plain page cannot
talk to the API without script.

## 1. Frontend hosting (top priority, user 2026-11-07)

Goal: a public URL for the frontend (`https://<name>.azurestaticapps.net`). Steps, in order, one commit each:

1. ~~Make the API base URL configurable at build time (was hard-coded `http://127.0.0.1:8000/api/v1` in `api.service.ts`).~~ **Done** 0cdb31b: `src/environments/environment.ts` (local) and `environment.production.ts` (live API) swapped by `fileReplacements`.
2. ~~Backend CORS: read extra allowed origins from an env var.~~ **Done** e36723b: `CORS_ALLOW_ORIGINS` (comma-separated).
3. ~~Terraform `azurerm_static_web_app` (Free, eastus2) plus outputs.~~ **Code done** be30b7d. User plan showed `1 to add, 0 to change, 0 to destroy`. The user then created the deploy-token GitHub secret, which implies the apply happened; the site URL is not yet confirmed to me.
4. Set the CORS origin on the Container App and add the frontend deploy step in CI.
   - ~~Terraform: `CORS_ALLOW_ORIGINS` env on the Container App.~~ **Done** 9010f7b; user applied. Verified 2026-11-07: a preflight from the site origin gets `access-control-allow-origin` echoed, an unknown origin gets 400.
   - ~~`.github/workflows/deploy-frontend.yml` (token upload, SPA fallback config).~~ **Done** 99005ce + 9321529 (dropped the invalid `skip_api_build` input). First two runs failed with "deployment_token provided was invalid" (secret set via a PowerShell pipe); the token was re-set with `--body` and the third run succeeded. Site: https://gray-sand-05d747c0f.4.azurestaticapps.net
5. Verify the live site end to end. **Partly verified** 2026-11-07: `/`, `/login`, `/workbench` return the Angular app (SPA fallback works), the served bundle calls the live API and no localhost, and a login request from the site origin reaches the API with CORS allowed (the API answered 403 "Password reset required" for an unknown email, by design). **Still unverified:** a real sign-in in a browser (needs an account in the live database; ask the user first).

## 2. UI (in order)

1. Login page as a real `<form>`. ~~Sign-in section: labels, `type=email`, native validation, Enter submits, `role="alert"` on errors.~~ **Done** 079e0e8. Still open: no demo prefills, bootstrap separated from sign-in, separate loading state per form.
2. Workbench page: replace raw JSON output/errors with `friendlyError`, then real forms and result views.
3. Page copy and shell: drop "Feature 1 Workbench" jargon; navigation and sign-out.
4. Success feedback (toast via `popover`, no library) and a responsive layout.
5. ~~Fix stale `src/app/app.spec.ts` ("Hello, app"), then run `ng test` in CI (the `frontend` job only built).~~ **Done** 63296ad (spec) and 494a9f4 (CI step; ran green on GitHub).
6. Frontend calls accept-invite and shows `inviteToken`.
7. End-to-end browser tests with Playwright, written adversarially (try to break sign-in: injection, double-submit, bad tokens, 4xx/5xx/offline). User chose Playwright option 1, 2026-11-07. Steps: (a) ~~harness + adversarial sign-in suite~~ **Done** (this commit): 37 Playwright tests, 3 stable runs by Melchior and 1 by me; hits a REAL local backend and throwaway Postgres (`equity_e2e`), with `page.route` only for labelled fault injection (the user chose real-backend UI tests, unit tests stay mocked); (b) run in CI with Chrome; (c) workbench flows; (d) run against the hosted site once step 5 of section 1 is done.

## 2b. Findings from the adversarial e2e suite (2026-11-07)

Each is pinned by a `test.fail()` test in `frontend/app/e2e/signin.spec.ts`; when fixed, remove `test.fail` and strike the item.

1. ~~**Account enumeration (medium, backend).** Unknown email -> 403 "Password reset required"; known email, wrong password -> 401 "Invalid credentials" (`app/api/routes/auth.py` login and institution_login). Same response for both, and keep the limiter counting.~~ **Done** (this commit): both login endpoints return 401 "Invalid credentials" for unknown email, NULL hash and wrong password, with a dummy argon2 verify against timing; failed attempts still count toward the limiter. The "Password reset required" state no longer exists in code.
2. **Token stored before it is decoded (low-medium, frontend).** `ApiService.institutionLogin` stores the token in `tap`, then `extractInstitutionId` can throw; the garbage token stays in localStorage and /workbench admits it.
3. **authGuard only checks non-empty (low, frontend).** Any string opens the /workbench shell; the API would still 401.
4. **Logout leaves `institutionId` in localStorage (low, frontend).** `clearTokens()` does not clear it.
5. Oddities: the password field keeps its value after a failed login; a 422 shows only the generic sentence, with no field-level message; the login page dumps the response JSON (token included) into a `<pre>` before navigating, which is fragile; 403/422 are not mapped by `friendlyError`.
6. Design observation: the backend allows one active token per user, so a second device or tab signing in kills the first session (it also made parallel e2e workers flaky).
7. ~~**Decision needed (user said "no account should ever not have a password").** Invited users have a NULL `passwordHash` until they accept the invite, so a NOT NULL migration would break invites unless the flow changes (e.g. invite creates the account only on accept). Not done.~~ **Decided** 2026-11-07: use an emailed invite LINK (not an emailed password); see section 2c.
8. **Risk for CI wiring:** the e2e suite hit load-related timeouts in 2 of 3 full parallel runs (many argon2 hashes at once: a 5 s alert wait, an Edge teardown). Re-runs passed. Before wiring it into CI, limit workers or raise the timeouts, and run it repeatedly.

## 2c. Invites by email and non-null passwords (user decision 2026-11-07)

The user wants every account to have a password and invites delivered by an emailed link. Steps, in order, one commit each:

1. ~~Frontend accept-invite page: reads the token from the link fragment (`#token=...`, never sent to servers or logs), sets the password via the existing accept-invite endpoint. First check the backend rejects reuse of an accepted token.~~ **Done** (this commit): `/accept-invite#token=...`, native form with no FormsModule, token removed from the address bar on load, invite-specific 401 message, 25 Karma specs. Reuse rejection is done in the backend (a6b9517). **Unverified:** no e2e test yet, not tried in a real browser against the backend.
2. ~~Migration: backfill NULL `passwordHash` with an unusable random hash, then make the column NOT NULL; new invites store the same kind of hash. Includes the invite-flow tests.~~ **Done** (this commit, migration 0005): both `passwordHash` columns NOT NULL; `users.passwordSetAt IS NULL` marks "invited, not accepted" and `accept_invite` rejects reuse by that marker. **Not yet applied to the live database** (the next backend deploy runs `alembic upgrade head` via the entrypoint; the user must OK the push).
3. Mail seam in the backend: `send_invite_email(to, link)` with a log/console backend for local use and tests. No provider yet.
4. Real provider (user to choose; recommended Azure Communication Services Email with the Azure-managed domain; needs Terraform, the user's `apply`, a connection-string secret, a new dependency through the pip-audit gate). Not verified that Terraform covers it; check first.
5. Wire sending into the invite flow and verify end to end with a real email to an address the user controls.

## 2d. CRUD the whole backend from the UI (user direction 2026-11-07)

Audit of `app/api/routes` on 2026-11-07: the API is almost write-only. Only two GETs exist (`/properties/{id}`, `/properties/{id}/owners`), there are no list endpoints, and no update or delete endpoints. So this is mostly BACKEND work first, then UI per entity.

| Entity (model) | Today | Missing for full CRUD |
|---|---|---|
| Institution | create (bootstrap, POST /institutions) | read, list, update, delete |
| InstitutionUser | create, login, revoke | list, read, update (role, name), delete/deactivate |
| User (owner) | register, login, accept-invite | read self, update profile/password, delete account |
| Property | create, read one | list, update, delete |
| PropertyAgreement | create (attach) | read, update, delete |
| UserProperty (owners/invites) | invite, list owners | update (ownership %), remove, re-invite |
| OwnerAcknowledgement | acknowledge | read (via property today) |
| EquityLedger, EquityTransfer, TransferClaim, Payment, PaymentCycle | models only, NO endpoints | everything |

Decisions needed from the user before building (these change what "delete" means): (1) who may do what (officer vs owner; per-institution isolation is mandatory); (2) soft delete (deactivate, keep history) vs hard delete, especially for anything financial; (3) the ledger/transfer/payment entities are probably append-only records: full CRUD there would be wrong, so confirm what "CRUD" should mean for them (create + read + correct-by-reversal, not edit/delete); (4) the equity business rules the ledger must keep (needs the user's domain knowledge).

Proposed order, one entity per run, each as API + tests (incl. cross-institution authorization tests) then UI (list, detail, create, edit, delete with a native `<dialog>` confirm): Property (list/update/delete) -> PropertyAgreement -> owners/UserProperty -> InstitutionUser -> Institution/profile -> financial entities last.

Progress and rules (user answer 2026-11-07: a property is removed only when an officer withdraws an un-sold house, or the owners split the house):

- ~~`GET /properties` list~~ **Done** (this commit): officers see their institution's properties, owners only their linked ones; `limit`/`offset`; 9 tests incl. cross-institution isolation. New dependency `require_user_or_institution_user` in `app/api/deps/auth.py`.
- Officer update of a property, its agreement and its owners: only while `pending_acknowledgement` (matches the existing lock once active).
- Officer delete: only while never activated; hard delete is acceptable then.
- Owner split of an ACTIVE property: needs all owners' consent, ends in a `dissolved` status and keeps history. **Blocked on the user:** what a split means for the loan (end co-ownership only, or separate properties/loans).
- ~~Gap found: `GET /properties/{id}` and `/owners` accept user tokens only; officers cannot read a single property. Add the dual dependency plus an institution check.~~ **Done** (this commit): officers read their own institution's property and owners list; another institution's property returns 404, identical to a nonexistent id. Minor leftover: an UNLINKED OWNER still gets 403 (not 404) for an existing property, so owners can probe for existing ids (UUIDs, low risk); the existing test pins that 403.

## 2e. Marketplace: buyers browse pending properties and connect with professionals (user direction 2026-11-07)

User statement: officers should be able to look at any pending property; any potential buyer could do that; buyers get connected with loan officers (LO), underwriters (UW) and brokers to get the house bought. This REVERSES the strict institution isolation built in 2d for PENDING properties only (active properties stay institution-scoped). My understanding, to be confirmed:

- Buyers are ordinary `User`s (self-register via `/register`); pending properties act as listings.
- LO / UW / broker are `role` values on institution users (today a free-text `role`, default `loan_officer`).
- A buyer sends a connection request to a professional about a property; the professional accepts or declines (new entity, e.g. `ConnectionRequest`: buyer, professional, property, status).

**Decided (user, one-word answer "Buyers", my reading):** buyers initiate connections (a buyer requests; the professional accepts or declines). If this reading is wrong, correct it here.

Decisions still needed before building: (1) which property fields a buyer or other-institution officer may see on a pending property (owners' names/emails and the agreement stay private; the seller's current balance and monthly payment are sensitive); (2) whether all three roles are institution users and whether buyers get a directory of professionals; (3) ~~how a connection works~~ buyer-initiated request/accept (see above); can an officer also assign, or is it buyer-only?

Then, one run each: a role vocabulary check; a public pending-listing endpoint with a restricted response schema (and tests that no private field leaks); a professionals directory; the ConnectionRequest model + migration + endpoints; UI for each.

## 3. Deploy hardening

- Tested rollback (needs a second revision; may need revisions-mode multiple and Terraform changes, ask first).
- Branch protection with required checks; a `production` GitHub environment with approval.
- Migrations handling (the entrypoint already runs alembic; unverified against the live Azure Postgres).

## 4. Static analysis

- bandit, then import-linter; one commit each.

## 5. Terraform state and pipeline

- Secrets out of state: ephemeral `random_password` + write-only attributes (verify azurerm 4.81 support).
- Remote encrypted Azure Storage backend (versioning, locking, `init -migrate-state`); needs the user's account.
- Plan on PRs with a read-only identity, then apply behind an approval environment (after remote state).

## 6. Smaller items

- ~~Complexity guardrails (ruff, no new dependency): enable `C901` (mccabe, max-complexity 8) and `PLR0911`/`PLR0912`/`PLR0913`/`PLR0915` (returns, branches, args, statements) in `pyproject.toml`. Measured 2026-11-07: zero findings today, so this is a free ratchet. Test = a throwaway function over the limit fails `ruff check`. Function length by lines has no ruff rule (`PLR0915` counts statements); `lizard` could add NLOC if wanted.~~ **Done** (this commit): mccabe 8 plus the four `PLR09xx` rules at pylint defaults; zero findings in the repo; a probe with 11 branches / 11 returns / 6 args fails `ruff check` (3 findings) and passes before the change. CI picks it up via plain `ruff check .`. `lizard` NLOC not added.
- Review the ~82 lines over 120 (now rewrapped) for structural causes (long query chains, deep nesting, fat route handlers). Complexity metrics show nothing wrong, so this is likely long strings/signatures, but it is unverified.
- ~~Ruff line-length 200 -> 120: set it in `pyproject.toml` and rewrap the lines over 120.~~ **Done** f799e16 (82 lines rewrapped with `ruff format` on the affected files).
- ~~Set `postgres_location` default to `canadacentral` in `infra/variables.tf`.~~ **Done** a163a2f. The user's plan showed no change to the Postgres server.
- ~~Migrate `@app.on_event` to a lifespan handler.~~ **Done** 5f8a62c (no deprecation warning; startup verified against a local Postgres).
- ~~alembic `env.py` `%` escaping bug.~~ **Done** 6f09807.
- ~~`.gitattributes` (`*.sh text eol=lf`) to stop CRLF checkouts of shell scripts.~~ **Done** 98cea4e. LF for requirements files was not added; those CRLF warnings are harmless.
- Resolve the `httpx` vs `httpx2` Starlette deprecation warning.
- Bump Node 20 actions (`actions/checkout@v4`, `setup-python@v5`, `azure/login@v2`) if newer majors exist.
- Dependabot and/or a scheduled pip-audit job (CI only audits at push time).
- Key Vault purge protection and network ACLs.
- Public Postgres plus the Azure-services firewall rule; README note on the cross-region database.
- Clean up the ghost `equitysplitter-pg` servers in eastus2.
- Audit log, password reset, atomic rate limiter; accessibility checks; GitHub repo description/topics.

## Decisions (user, 2026-11-07)

- Ruff line length: shorten from 200 to 120; revisit 88 later. *Applied: f799e16.*
- Postgres region: canadacentral (eastus2 failed). *Applied: a163a2f.*
- Frontend errors: the more HTML-native scheme. Inline native validation (`:user-invalid`) plus a `role="alert"` region for server errors; `popover` toasts for confirmations; no library. *In progress (sign-in form done).*
- Backlog items are struck through, never deleted (governance/audit trail). *Applied: this file.*

## Open decisions (user)

- Do the Terraform state-secrets work before or after the remaining deploy work (leaning after)?

## Not yet verified

- Token behaviour live (the deploy smoke test only hits `/health`).
- Rollback commands.
- ~~That Terraform ignores the image and port changes against real state.~~ **Verified** 2026-11-07: the user's `terraform plan` showed `0 to change` for the Container App.
- The CI `pip-audit` step only guards pushes; a CVE published later is caught on the next run.
- ~~The frontend deploy workflow and the hosted site have never run; the CORS env var is not applied.~~ **Verified** 2026-11-07, see section 1 steps 4-5.
- A real browser sign-in on the hosted site; the first account on the live database.

## Done (earlier work, before this file existed)

- ~~Dependency CVEs.~~ **Done**: fastapi/starlette 0fc6816, PyJWT 917cbc9, pytest/httpx moved to dev 627a109, pip-audit CI gate 6cde252 (ran green on GitHub).
- ~~Intermittent CI failure.~~ **Done** 18a8f30: SQLite NUMERIC affinity on `postgresql.UUID` in tests, fixed with a `CHAR(32)` hook plus a regression test.
- ~~Login page shows raw JSON errors.~~ **Done** 9239553: plain-language errors via `friendlyError`.
