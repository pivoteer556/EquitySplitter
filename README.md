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
- **Login rate limiting** (`/auth/login`, `/auth/institution/login`): 5 failed attempts per 60 s per email+IP return
  HTTP 429 with `Retry-After`. It is in-memory per process, so it does not span multiple replicas or survive a
  restart (move the counters to Redis/DB to scale out). The key uses the direct socket IP; there is no
  `X-Forwarded-For` handling, so behind a reverse proxy clients effectively share one IP. `/auth/register` and
  `/auth/institution/bootstrap` are not limited.
- Known gap: invited owners are created without a password and there is no invite-accept / password-set flow yet.

## Tests and CI
`python -m pytest` runs the equity math, password hashing (including legacy-hash upgrade), and API tests
(auth, revocation, property/agreement/acknowledgement flow) against in-memory SQLite.
GitHub Actions (`.github/workflows/ci.yml`) runs the tests on Python 3.12 and 3.14, applies the Alembic
migrations to a real Postgres, builds the Angular frontend, and builds the Docker image.

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
- `GET /api/v1/properties/{propertyId}`
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
