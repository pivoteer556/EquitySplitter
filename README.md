# Equity Splitter API

FastAPI + PostgreSQL project scaffolded from the shared mortgage equity ERD.

## Stack
- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- Alembic
- pytest

[![CI](https://github.com/pivoteer556/EquitySplitter/actions/workflows/ci.yml/badge.svg)](https://github.com/pivoteer556/EquitySplitter/actions/workflows/ci.yml)

Design specs and schema diagrams live in [docs/specs/](docs/specs/).

## Security design notes
- **Passwords** are hashed with argon2id (`argon2-cffi`, library defaults; the salt is embedded in the
  encoded hash). Accounts created before this change used salted SHA-256; those hashes still verify and are
  transparently re-hashed with argon2id on the owner's next successful login, after which `passwordSalt` is cleared.
- **JWT signing keys** are generated server-side, stored in the `authSecretState` table, and rotated every
  `JWT_ROTATION_DAYS`. The previous key stays valid for one rotation period so in-flight tokens survive.
  Keeping keys in the database (not only in env) lets every API instance share and rotate the same key without a
  redeploy; the trade-off is that a database leak exposes signing keys, so the DB must be treated as a
  secret store. Tokens are also pinned to a server-side `lastTokenIssuedAt`, so only the latest token per account
  is accepted and institution users can be revoked.
- **Rate limiting** — logins (`/auth/login`, `/auth/institution/login`): 5 failed attempts per 60 s per email+IP return
  HTTP 429 with `Retry-After`. Counters live in the database (`rateLimitHits`, keyed by a SHA-256 of the
  scope+IP+email, so no email/IP is stored), which makes them shared across replicas and durable across restarts.
  Check-then-record is not atomic, so concurrent requests can slip a few attempts past the threshold.
  The key uses the socket IP unless `TRUSTED_PROXY_HOPS` is set to the number of reverse proxies in front of the app
  (Azure Container Apps ingress: `1`), in which case the client IP is the Nth entry from the right of
  `X-Forwarded-For`. Leave it at `0` when not behind a proxy, otherwise clients could dodge the limit by spoofing the
  header; set it correctly behind one, otherwise all clients share an IP and one user could lock another out.
  `/auth/register` and `/auth/institution/bootstrap` share a budget of 10 attempts per hour per IP (accepted or
  rejected, so duplicate-email probing is not free), also returning 429 with `Retry-After`.
  `/auth/accept-invite` uses the same limit (10 attempts per hour per IP, every attempt counted) but with its own
  per-IP budget, separate from register/bootstrap. These are per-IP application-level throttles against guessing and
  abuse, not DDoS protection; volumetric attacks must be absorbed at the edge (e.g. Azure Front Door / WAF).
- **CORS** — `http://localhost:4200` and `http://127.0.0.1:4200` are always allowed. Set `CORS_ALLOW_ORIGINS` to a
  comma-separated list of extra origins (e.g. `https://site.example.net,https://other.example`) to allow a deployed
  frontend. Whitespace, empty entries, trailing slashes and `*` are ignored.
- **Bootstrap gate: setup token AND platform admin** — `POST /auth/institution/bootstrap` (creating an institution)
  requires BOTH the header `X-Bootstrap-Token` equal to the `BOOTSTRAP_TOKEN` setting (constant-time compare) AND an
  `Authorization: Bearer` token of a signed-in platform admin (a `users` row with `isPlatformAdmin` true and no
  institution; a normal user token from `POST /auth/login`). Leave `BOOTSTRAP_TOKEN` empty to disable the endpoint. A
  disabled endpoint, a missing or wrong token, and a missing, bad, expired or non-admin bearer all return the same
  `404 Not found`, so the endpoint is not discoverable and a response never says which check failed; the checks run in
  the order rate limit, setup token, admin bearer, and every attempt counts against the signup rate limit. On success
  the admin's session rotates (`X-Refreshed-Token`). Nothing public creates or promotes a platform admin, and
  `/auth/register` ignores `isPlatformAdmin`. The Terraform setup token (`terraform output -raw bootstrap_token`) is
  still required in addition to the admin. Known limits: ordinary accounts cannot be promoted; a platform admin who is
  locked out has no recovery until the password-reset flow exists (BACKLOG 2l); the script does not validate email
  format; migration 0011 has no test with pre-existing rows. Since 2026-11-09 (`/buyer` removed) the admin signs in on the
  one `/login` screen, then opens `/bootstrap` by URL (tokens carry no platform-admin flag yet; planned).
- **Creating the first platform admin (operator)** — nobody can sign in to create the first admin, so an operator runs
  `python -m scripts.create_platform_admin <email>` with `DATABASE_URL` pointing at the target database (apply
  migrations first, `alembic upgrade head`). The script takes no password and prints a one-time
  `/accept-invite#token=...` link (7 days, single use, same generator as owner invites); open it on the frontend and set
  a password, then sign in. It exits 1 for an email that already belongs to an ordinary account (no promotion). Running
  it again for an admin who already set a password prints a link that `accept-invite` refuses (single use) and a note
  on stderr. For the live Azure database the user runs it (or the agent asks first): one possible route is
  `az containerapp exec` into the running app, which is UNVERIFIED and has not been tried. IMPORTANT after the deploy
  that ships this: no live bootstrap is possible until the operator has created the first platform admin.
- Invited owners start without a password. When the invitee has none, `POST /properties/{id}/owners` returns an
  `inviteToken` (re-inviting issues a fresh one); the loan officer hands it over out-of-band and the invitee POSTs
  `{token, password}` to `/auth/accept-invite` to set a password and get an access token. Tokens expire after 7 days
  and are single-use via the `passwordSetAt` marker (NULL until the invite is accepted); they are stateless, so one can only be invalidated by the user
  setting a password or by key rotation.
- Known gaps: no email delivery of invites and no password-reset flow for existing users.

## Tests and CI
`python -m pytest` runs the equity math, password hashing (including legacy-hash upgrade), and API tests
(auth, revocation, property/agreement/acknowledgement flow) against in-memory SQLite.
GitHub Actions (`.github/workflows/ci.yml`) runs the tests on Python 3.12 and 3.14, applies the Alembic
migrations to a real Postgres, builds the Angular frontend, and builds the Docker image.

## Hosting (Azure)
`infra/` holds Terraform for Azure: Container Apps (scale to zero), Container Registry, Postgres Flexible Server
(B1ms), Key Vault, a Static Web App (Free) for the frontend, and a GitHub OIDC identity for the deploy workflow.
The Static Web App needs `az provider register --namespace Microsoft.Web --wait` once; the hosted site is not yet
deployed or verified. CI only runs `terraform fmt -check` and `validate`.

The deploy workflow (`.github/workflows/deploy.yml`) runs after CI passes on master. It builds the image and pushes
it to ACR, switches the ingress port to 8000, updates the Container App, then smoke-tests it with
`scripts/smoke_test.sh`, which fails the deploy unless `GET /health` returns HTTP 200 (it retries for up to 120 s,
since the app scales to zero; override with `SMOKE_TIMEOUT_SECONDS`). The first deploy was confirmed live on
2026-11-07: `/health` returns `{"status":"ok"}`. The root path returns 404 `{"detail":"Not Found"}`, which is
expected: this is an API with no page at `/`.

Apply it yourself (needs rights to create Entra app registrations and role assignments):
```
az login --tenant 592061b2-fe76-4480-9da8-8d8b76596315
cd infra
terraform init
terraform apply -var subscription_id=<id>
```
`github_repository` defaults to `pivoteer556/EquitySplitter`; pass `-var github_repository=owner/name` to change it.

- Secrets are generated by Terraform (alphanumeric) and stored in Key Vault; read one with
  `az keyvault secret show --vault-name $(terraform output -raw key_vault_name) --name postgres-admin-password --query value -o tsv`
  (also `jwt-secret-seed`, `bootstrap-token`). The applying identity has Key Vault Secrets Officer.
- `terraform output -raw bootstrap_token` prints the setup token that gates institution creation (the `BOOTSTRAP_TOKEN` env var on the Container App).
- State is local (`terraform.tfstate`, gitignored) and contains the generated secrets in plain text: back it up, never commit it.
- Add these outputs as GitHub repo variables for the deploy workflow: `tenant_id`, `subscription_id`,
  `github_client_id`, `key_vault_name`, `resource_group_name`, `acr_name`, `container_app_name`
  (`terraform output <name>`). None are secret.

Accepted risks and caveats:
- Postgres is publicly reachable (with the "allow Azure services" firewall rule); there is no VNet.
- The first apply creates the Container App from a public placeholder image (`mcr.microsoft.com/k8se/quickstart`)
  with ingress on port 80; the deploy workflow switches the image and the ingress port (8000), and Terraform ignores
  later changes to both.

### Rollback (NOT YET TESTED)
Container Apps keep prior revisions, so a bad deploy should be reversible, but none of this has been tried here:
```
az containerapp revision list -n equitysplitter-api -g Equity-Splitter-Dev -o table
az containerapp ingress traffic set -n equitysplitter-api -g Equity-Splitter-Dev --revision-weight <previous-revision>=100
```
Uncertainty: the app is in single-revision mode by default, where only the latest revision is active and receives
all traffic. You may first need `az containerapp revision activate` on the old revision and/or switch the app to
multiple-revision mode (`az containerapp revision set-mode --mode multiple`) before traffic can be split.

## Run
1. Create and activate a virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Copy env file:
   copy .env.example .env
4. Run migrations:
   alembic upgrade head
5. Start API:
   uvicorn app.main:app --reload

## One-Command Local Dev
From the repo root:
`powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1`

Optional flags:
- `-SkipInstall` skip pip install
- `-SkipMigrate` skip alembic migration
- `-SkipTests` skip pytest quality gate

The script creates a local test user with a newly generated password and prints
the credentials in the terminal. The password is not stored in the repository.

## Run With Docker Compose
1. Start services:
   docker compose up --build
2. API will be available at:
   http://localhost:8000
3. Stop services:
   docker compose down

Notes:
- The API container waits for Postgres, runs `alembic upgrade head`, then starts Uvicorn.
- Postgres data is persisted in the `postgres_data` Docker volume.

## Endpoints (Feature 1)
- `POST /api/v1/auth/institution/bootstrap`
- `POST /api/v1/auth/institution/login`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/institutions`
- `POST /api/v1/institution-users`
- `POST /api/v1/properties`
- `POST /api/v1/properties/{propertyId}/agreement`
- `POST /api/v1/properties/{propertyId}/owners`
- `POST /api/v1/properties/{propertyId}/acknowledge`
- `GET /api/v1/properties` (officer: own institution; owner: linked properties; `limit` 1-200 default 100, `offset`)
- `GET /api/v1/professionals` (any buyer or officer: directory of institution users whose role is `loan_officer`, `underwriter` or `broker`, restricted to `id`, `name`, `role`, `institutionName`; no email or institution id; optional `role` filter, unknown role is 422; ordered by name then id; `limit` 1-200 default 100, `offset`)
- `POST /api/v1/connection-requests` (buyer token only; body `professionalId`, `propertyId`, optional `message` up to 1000 chars; creates a `pending` request, 201. 404 `Professional not found` for a missing professional or one outside the role vocabulary, 404 `Property not found` for a missing or non-pending property, 409 `Connection already requested` for a repeat, 409 `Already an owner of this property`; response has no buyer email or institution ids)
- `GET /api/v1/connection-requests` (buyer: own requests; professional: only requests addressed to that very institution user, not colleagues', plus `buyerName` and never the email; `limit` 1-200 default 100, `offset`; newest first)
- `GET /api/v1/listings` (any owner/buyer or officer, any institution: pending properties only, restricted to `id`, `address`, `status`, `createdAt`; no loan, agreement or owner data; `limit` 1-200 default 100, `offset`)
- `GET /api/v1/properties/{propertyId}`
- `PATCH /api/v1/properties/{propertyId}` (officer of the property's institution, only while not active; partial update of address, loanAmount, currentBalance, monthlyPayment, dynamicBillingEnabled; unknown fields, nulls, empty body: 422)
- `DELETE /api/v1/properties/{propertyId}` (officer of the property's institution, only while not active; hard delete of the property, agreement, loan and owner links, owner accounts stay; 204; other institution or missing: 404; active: 403)
- `GET /api/v1/properties/{propertyId}/owners`
- `GET /health`

## Angular Frontend (Local)
1. In one terminal, run backend:
   `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1`
2. In a second terminal, run frontend:
   `cd frontend\app`
   `npm.cmd install`
   `npm.cmd start`
3. Open:
   `http://localhost:4200`
