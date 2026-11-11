"""Authentication dependencies.

Session rotation lives in ONE place, not here and not in handlers: the dependencies below authenticate and, unless
they are a *_no_rotation variant, record on request.state that the caller's stored session token is due for
rotation. RotatingRoute (app/api/route.py) performs it after the response is produced, only when the status is
below 400, so a rejected request never strands the caller with a dead token and handlers contain no rotation code.
"""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import InstitutionUser, User
from app.services.auth import (
    decode_token,
    ensure_institution_not_revoked,
    ensure_user_property_scope,
    validate_active_token_iat,
)


@dataclass
class Principal:
    user_id: UUID
    user_type: str
    institution_id: UUID | None = None


PENDING_ROTATION = "pending_rotation"  # request.state attribute: the Principal whose session RotatingRoute rotates


def _record_rotation(request: Request, principal: Principal) -> Principal:
    setattr(request.state, PENDING_ROTATION, principal)
    return principal


def _extract_bearer(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def _user_principal(db: Session, claims: dict) -> Principal:
    if claims.get("userType") != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong identity type for endpoint")

    user_id = UUID(claims["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    validate_active_token_iat(user.lastTokenIssuedAt, claims.get("iat"))
    return Principal(user_id=user.id, user_type="user")


def _institution_principal(db: Session, claims: dict) -> Principal:
    if claims.get("userType") != "institution_user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong identity type for endpoint")

    user_id = UUID(claims["sub"])
    inst_user = db.query(InstitutionUser).filter(InstitutionUser.id == user_id).first()
    if inst_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Institution user not found")

    ensure_institution_not_revoked(db, inst_user.id)
    validate_active_token_iat(inst_user.lastTokenIssuedAt, claims.get("iat"))
    return Principal(user_id=inst_user.id, user_type="institution_user", institution_id=inst_user.institutionId)


def require_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    claims = decode_token(db, _extract_bearer(authorization))
    return _record_rotation(request, _user_principal(db, claims))


def require_institution_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    claims = decode_token(db, _extract_bearer(authorization))
    return _record_rotation(request, _institution_principal(db, claims))


def require_institution_user_no_rotation(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Authenticates an officer but never rotates the session. The visible opt-out, for revoke: a self-revoke kills
    the caller's token, so a refreshed one would be dead on arrival."""
    claims = decode_token(db, _extract_bearer(authorization))
    return _institution_principal(db, claims)


def require_user_or_institution_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Accept either identity type; any other userType (e.g. invite) gets the usual 403 from _user_principal."""
    claims = decode_token(db, _extract_bearer(authorization))
    if claims.get("userType") == "institution_user":
        return _record_rotation(request, _institution_principal(db, claims))
    return _record_rotation(request, _user_principal(db, claims))


def platform_admin_principal(request: Request, db: Session, authorization: str | None) -> Principal:
    """A signed-in platform admin (a "user" session whose account has isPlatformAdmin). Raises HTTPException on any
    failure; callers that must not leak why (bootstrap) map every failure to one response. Records the admin's
    session for rotation like the other dependencies, so a rejected caller never has their stored session replaced."""
    claims = decode_token(db, _extract_bearer(authorization))
    if claims.get("userType") != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong identity type for endpoint")
    user = db.query(User).filter(User.id == UUID(claims["sub"])).first()
    if user is None or not user.isPlatformAdmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a platform admin")
    return _record_rotation(request, _user_principal(db, claims))


def require_user_property_scope(
    property_id: UUID,
    principal: Principal,
    db: Session,
) -> None:
    ensure_user_property_scope(db, principal.user_id, property_id)
