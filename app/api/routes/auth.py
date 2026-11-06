from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, require_institution_user
from app.core.config import settings
from app.db.session import get_db
from app.models import InstitutionUser, TokenRevocation, User
from app.schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    InstitutionBootstrapRequest,
    InstitutionBootstrapResponse,
    InstitutionRevokeRequest,
)
from app.services.auth import (
    bootstrap_institution,
    hash_password,
    refresh_and_store_institution_token,
    refresh_and_store_user_token,
    validate_password_policy,
    verify_and_upgrade_password,
)
from app.services.rate_limit import login_limiter

router = APIRouter(prefix="/auth")


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_hops
    if hops <= 0:
        return peer  # never trust X-Forwarded-For unless we know how many proxies append to it
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    # Each trusted proxy appends the peer it saw, so the real client is the Nth entry from the right.
    return forwarded[-hops] if len(forwarded) >= hops else peer


def _login_key(scope: str, request: Request, email: str) -> str:
    return f"{scope}:{_client_ip(request)}:{email.strip().lower()}"


def _fail_login(key: str, status_code: int, detail: str):
    login_limiter.record_failure(key)
    raise HTTPException(status_code=status_code, detail=detail)


def _enforce_login_limit(key: str) -> None:
    wait = login_limiter.retry_after(key)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts",
            headers={"Retry-After": str(wait)},
        )


@router.post("/institution/bootstrap", response_model=InstitutionBootstrapResponse, status_code=status.HTTP_201_CREATED)
def institution_bootstrap(payload: InstitutionBootstrapRequest, db: Session = Depends(get_db)):
    institution, officer, token = bootstrap_institution(
        db,
        payload.institutionName,
        payload.officerName,
        payload.officerEmail,
        payload.officerPassword,
    )
    return InstitutionBootstrapResponse(
        accessToken=token,
        institution=institution,
        institutionUser=officer,
    )


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)):
    validate_password_policy(payload.password)
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(name=payload.name, email=payload.email, passwordHash=hash_password(payload.password))
    db.add(user)
    db.flush()
    token = refresh_and_store_user_token(db, user)
    return AuthTokenResponse(accessToken=token)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: AuthLoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _login_key("user", request, payload.email)
    _enforce_login_limit(key)
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or user.passwordHash is None:
        _fail_login(key, status.HTTP_403_FORBIDDEN, "Password reset required")
    if not verify_and_upgrade_password(db, user, payload.password):
        _fail_login(key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    login_limiter.reset(key)
    token = refresh_and_store_user_token(db, user)
    return AuthTokenResponse(accessToken=token)


@router.post("/institution/login", response_model=AuthTokenResponse)
def institution_login(payload: AuthLoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _login_key("institution", request, payload.email)
    _enforce_login_limit(key)
    inst_user = db.query(InstitutionUser).filter(InstitutionUser.email == payload.email).first()
    if inst_user is None or inst_user.passwordHash is None:
        _fail_login(key, status.HTTP_403_FORBIDDEN, "Password reset required")
    if not verify_and_upgrade_password(db, inst_user, payload.password):
        _fail_login(key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    login_limiter.reset(key)
    token = refresh_and_store_institution_token(db, inst_user)
    return AuthTokenResponse(accessToken=token)


@router.post("/institution/revoke", status_code=status.HTTP_204_NO_CONTENT)
def institution_revoke(
    payload: InstitutionRevokeRequest,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    target_id = principal.user_id if payload.institutionUserId is None else UUID(payload.institutionUserId)
    if target_id != principal.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin revoke not enabled")

    target = db.query(InstitutionUser).filter(InstitutionUser.id == target_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution user not found")

    revocation = TokenRevocation(institutionUserId=target.id, revokedBy=None)
    target.lastTokenIssuedAt = datetime.now(timezone.utc).replace(microsecond=0)
    db.add(revocation)
    db.commit()
    return None
