# Equity Splitter API

FastAPI + PostgreSQL project scaffolded from the shared mortgage equity ERD.

## Stack
- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- Alembic
- pytest

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
