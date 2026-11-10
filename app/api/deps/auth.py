from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import InstitutionUser, User
from app.services.auth import (
    decode_token,
    ensure_institution_not_revoked,
    ensure_user_property_scope,
    refresh_and_store_institution_token,
    refresh_and_store_user_token,
    validate_active_token_iat,
)


@dataclass
class Principal:
    user_id: UUID
    user_type: str
    institution_id: UUID | None = None


def _extract_bearer(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def require_user(
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    claims = decode_token(db, _extract_bearer(authorization))
    return _user_principal(response, db, claims)


def require_user_unrotated(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Like require_user but leaves the stored session token alone. For endpoints that can reject the caller AFTER
    authentication (404/409/422): those responses cannot carry X-Refreshed-Token, so rotating first would strand the
    caller with a dead token. Such an endpoint rotates itself, after success, with refresh_and_store_user_token."""
    claims = decode_token(db, _extract_bearer(authorization))
    return _user_principal(None, db, claims)


def _user_principal(response: Response | None, db: Session, claims: dict) -> Principal:
    if claims.get("userType") != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong identity type for endpoint")

    user_id = UUID(claims["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    validate_active_token_iat(user.lastTokenIssuedAt, claims.get("iat"))
    if response is not None:
        response.headers["X-Refreshed-Token"] = refresh_and_store_user_token(db, user)
    return Principal(user_id=user.id, user_type="user")


def platform_admin_principal(response: Response, db: Session, authorization: str | None) -> Principal:
    """A signed-in platform admin (a "user" session whose account has isPlatformAdmin). Raises HTTPException on any
    failure; callers that must not leak why (bootstrap) map every failure to one response. The admin flag is checked
    BEFORE the session token is rotated, so a rejected caller never has their stored session replaced."""
    claims = decode_token(db, _extract_bearer(authorization))
    if claims.get("userType") != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong identity type for endpoint")
    user = db.query(User).filter(User.id == UUID(claims["sub"])).first()
    if user is None or not user.isPlatformAdmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a platform admin")
    return _user_principal(response, db, claims)


def require_institution_user(
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    claims = decode_token(db, _extract_bearer(authorization))
    return _institution_principal(response, db, claims)


def require_institution_user_unrotated(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Like require_institution_user but leaves the stored session token alone. For endpoints that can reject the
    caller AFTER authentication (a wrong TOTP code): a 401 cannot carry X-Refreshed-Token, so rotating first would
    strand the caller with a dead token. Such an endpoint rotates itself, after success, with
    refresh_and_store_institution_token."""
    claims = decode_token(db, _extract_bearer(authorization))
    return _institution_principal(None, db, claims)


def _institution_principal(response: Response | None, db: Session, claims: dict) -> Principal:
    if claims.get("userType") != "institution_user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong identity type for endpoint")

    user_id = UUID(claims["sub"])
    inst_user = db.query(InstitutionUser).filter(InstitutionUser.id == user_id).first()
    if inst_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Institution user not found")

    ensure_institution_not_revoked(db, inst_user.id)
    validate_active_token_iat(inst_user.lastTokenIssuedAt, claims.get("iat"))
    if response is not None:
        response.headers["X-Refreshed-Token"] = refresh_and_store_institution_token(db, inst_user)
    return Principal(user_id=inst_user.id, user_type="institution_user", institution_id=inst_user.institutionId)


def require_user_or_institution_user(
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Accept either identity type; any other userType (e.g. invite) gets the usual 403 from require_user."""
    claims = decode_token(db, _extract_bearer(authorization))
    if claims.get("userType") == "institution_user":
        return _institution_principal(response, db, claims)
    return _user_principal(response, db, claims)


def require_user_property_scope(
    property_id: UUID,
    principal: Principal,
    db: Session,
) -> None:
    ensure_user_property_scope(db, principal.user_id, property_id)
