from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, require_institution_user_unrotated, rotate_session
from app.db.session import get_db
from app.models import InstitutionUser, TotpCredential
from app.services import auth as auth_service
from app.services import totp
from app.services.rate_limit import login_limiter

router = APIRouter(prefix="/auth/institution/totp")


class TotpEnrollment(BaseModel):
    secret: str
    otpauthUri: str


class TotpConfirm(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


def _credential(db: Session, user_id) -> TotpCredential | None:
    return db.query(TotpCredential).filter(TotpCredential.institutionUserId == user_id).first()


@router.post("/enroll", response_model=TotpEnrollment)
def enroll(
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    """Start (or restart, until confirmed) enrolment. The secret is returned once, here, and never again.
    The session token rotates only on success (a 409 cannot carry X-Refreshed-Token),
    as in regenerate_recovery_codes."""
    credential = _credential(db, principal.user_id)
    if credential is not None and credential.confirmedAt is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Authenticator already set up")
    officer = db.get(InstitutionUser, principal.user_id)
    assert officer is not None  # the auth dependency just loaded this row
    secret = totp.new_secret()
    if credential is None:
        credential = TotpCredential(institutionUserId=principal.user_id, secretEncrypted=totp.encrypt_secret(secret))
        db.add(credential)
    else:
        credential.secretEncrypted = totp.encrypt_secret(secret)
    db.commit()
    rotate_session(db, principal, response)
    return TotpEnrollment(secret=secret, otpauthUri=totp.provisioning_uri(secret, officer.email))


@router.post("/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm(
    payload: TotpConfirm,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    """Rotate the session token only after the code is accepted: 400/409/429 cannot carry X-Refreshed-Token."""
    key = f"totp:{principal.user_id}"
    wait = login_limiter.retry_after(db, key)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts",
            headers={"Retry-After": str(wait)},
        )
    credential = _credential(db, principal.user_id)
    if credential is not None and credential.confirmedAt is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Authenticator already set up")
    step = None
    if credential is not None:
        step = totp.verify_code(
            totp.decrypt_secret(credential.secretEncrypted), payload.code, auth_service.now_utc_seconds(), None
        )
    if credential is None or step is None:
        login_limiter.record_attempt(db, key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    login_limiter.reset(db, key)
    credential.confirmedAt = datetime.now(UTC)
    credential.lastUsedStep = step
    db.commit()
    rotate_session(db, principal, response)
    return None
