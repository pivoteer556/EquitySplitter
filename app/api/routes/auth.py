from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, require_institution_user
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

router = APIRouter(prefix="/auth")


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
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or user.passwordHash is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password reset required")
    if not verify_and_upgrade_password(db, user, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = refresh_and_store_user_token(db, user)
    return AuthTokenResponse(accessToken=token)


@router.post("/institution/login", response_model=AuthTokenResponse)
def institution_login(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    inst_user = db.query(InstitutionUser).filter(InstitutionUser.email == payload.email).first()
    if inst_user is None or inst_user.passwordHash is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password reset required")
    if not verify_and_upgrade_password(db, inst_user, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
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
