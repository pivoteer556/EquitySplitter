param(
    [switch]$SkipInstall,
    [switch]$SkipMigrate,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPath = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[dev] Creating virtual environment..."
    py -3.12 -m venv $VenvPath
}

Write-Host "[dev] Using virtual environment at $VenvPath"

if (-not $SkipInstall) {
    Write-Host "[dev] Installing dependencies..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "[dev] pip upgrade failed." }
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "[dev] dependency installation failed." }
}

if (-not (Test-Path ".env")) {
    Write-Host "[dev] Creating .env from .env.example..."
    Copy-Item .env.example .env
}

if (-not $SkipMigrate) {
    Write-Host "[dev] Running Alembic migrations..."
    & $VenvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "[dev] alembic migration failed." }
}

Write-Host "[dev] Seeding default institutional test user..."
@'
import secrets

from app.db.session import SessionLocal
from app.models import Institution, InstitutionUser
from app.services.auth import create_salt, hash_password

USERNAME = "wilkenia"
PASSWORD = secrets.token_urlsafe(24)
EMAIL = "wilkenia@equitysplitter.local"
INSTITUTION_NAME = "Wilkenia Lending"

db = SessionLocal()
try:
    institution = db.query(Institution).filter(Institution.name == INSTITUTION_NAME).first()
    if institution is None:
        institution = Institution(name=INSTITUTION_NAME)
        db.add(institution)
        db.flush()

    user = db.query(InstitutionUser).filter(InstitutionUser.email == EMAIL).first()
    salt = create_salt()
    password_hash = hash_password(PASSWORD, salt)

    if user is None:
        user = InstitutionUser(
            institutionId=institution.id,
            name=USERNAME,
            email=EMAIL,
            role="loan_officer",
            passwordSalt=salt,
            passwordHash=password_hash,
        )
        db.add(user)
    else:
        user.name = USERNAME
        user.role = "loan_officer"
        user.institutionId = institution.id
        user.passwordSalt = salt
        user.passwordHash = password_hash

    db.commit()
    print(f"[dev] Default test user ready: {EMAIL}")
    print(f"[dev] Default test user password (local only): {PASSWORD}")
finally:
    db.close()
'@ | & $VenvPython -
if ($LASTEXITCODE -ne 0) { throw "[dev] default user seed failed." }

if (-not $SkipTests) {
    Write-Host "[dev] Running tests..."
    & $VenvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "[dev] test run failed." }
}

Write-Host "[dev] Starting API at http://127.0.0.1:8000"
& $VenvPython -m uvicorn app.main:app --reload
