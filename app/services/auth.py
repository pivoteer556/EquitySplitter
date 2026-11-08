import base64
import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuthSecretState, Institution, InstitutionUser, TokenRevocation, User, UserProperty

PASSWORD_POLICY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$")

INVITE_TOKEN_DAYS = 7


def now_utc_seconds() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _derive_secret(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def ensure_secret_state(db: Session) -> AuthSecretState:
    state = db.query(AuthSecretState).first()
    if state is None:
        state = AuthSecretState(
            currentSecret=_derive_secret(f"{settings.jwt_secret_seed}:{secrets.token_hex(16)}"),
            previousSecret=None,
            rotatedAt=now_utc_seconds(),
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def maybe_rotate_secrets(db: Session) -> None:
    state = ensure_secret_state(db)
    due_at = state.rotatedAt + timedelta(days=settings.jwt_rotation_days)
    if now_utc_seconds() < due_at:
        return
    state.previousSecret = state.currentSecret
    state.currentSecret = _derive_secret(f"{settings.jwt_secret_seed}:{secrets.token_hex(16)}")
    state.rotatedAt = now_utc_seconds()
    db.commit()


_hasher = PasswordHasher()  # argon2id with library defaults; salt is generated and embedded in the hash


def hash_password(password: str) -> str:
    return _hasher.hash(password)


_DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time-login")


def burn_password_check(password: str) -> None:
    """Spend one argon2 verification so a missing or hash-less account takes as long as a wrong password."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except VerificationError:
        pass


def _verify_legacy_sha256(password: str, salt: str, password_hash: str) -> bool:
    candidate = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return hmac.compare_digest(candidate, password_hash)


def validate_password_policy(password: str) -> None:
    if not PASSWORD_POLICY.match(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Password does not meet policy requirements"
        )


def issue_token(db: Session, subject_id: UUID, user_type: str, institution_id: UUID | None = None) -> str:
    state = ensure_secret_state(db)
    iat_dt = now_utc_seconds()
    claims = {
        "sub": str(subject_id),
        "userType": user_type,
        "iat": int(iat_dt.timestamp()),
        "exp": int((iat_dt + timedelta(minutes=settings.jwt_exp_minutes)).timestamp()),
    }
    if institution_id is not None:
        claims["institutionId"] = str(institution_id)
    return jwt.encode(claims, state.currentSecret, algorithm="HS256")


def issue_invite_token(db: Session, user_id: UUID) -> str:
    """Signed, stateless invite token (no DB row, no lastTokenIssuedAt). userType="invite" keeps it out of every
    auth dependency, which only accept "user"/"institution_user". Single-use is enforced by accept_invite
    (passwordHash must still be unset)."""
    iat_dt = now_utc_seconds()
    claims = {
        "sub": str(user_id),
        "userType": "invite",
        "iat": int(iat_dt.timestamp()),
        "exp": int((iat_dt + timedelta(days=INVITE_TOKEN_DAYS)).timestamp()),
    }
    return jwt.encode(claims, ensure_secret_state(db).currentSecret, algorithm="HS256")


def decode_token(db: Session, token: str) -> dict:
    state = ensure_secret_state(db)
    secrets_to_try = [state.currentSecret]
    if state.previousSecret:
        secrets_to_try.append(state.previousSecret)
    for secret in secrets_to_try:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            continue
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def verify_and_upgrade_password(db: Session, account: User | InstitutionUser, password: str) -> bool:
    """Check a password against an account, transparently upgrading legacy salted-SHA-256 hashes to argon2id."""
    stored = account.passwordHash
    if stored is None:
        return False
    if stored.startswith("$argon2"):
        try:
            _hasher.verify(stored, password)
        except (VerificationError, InvalidHashError):
            return False
        if _hasher.check_needs_rehash(stored):
            account.passwordHash = hash_password(password)
            db.commit()
        return True
    if account.passwordSalt is None or not _verify_legacy_sha256(password, account.passwordSalt, stored):
        return False
    account.passwordHash = hash_password(password)
    account.passwordSalt = None
    db.commit()
    return True


def validate_active_token_iat(stored: datetime | None, token_iat: int | None) -> None:
    if stored is None or token_iat is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token session")
    if stored.tzinfo is None:  # SQLite drops tzinfo; values are always stored as UTC
        stored = stored.replace(tzinfo=UTC)
    if int(stored.timestamp()) != token_iat:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no longer active")


def refresh_and_store_user_token(db: Session, user: User) -> str:
    token = issue_token(db, user.id, "user")
    claims = decode_token(db, token)
    user.lastTokenIssuedAt = datetime.fromtimestamp(claims["iat"], tz=UTC)
    db.commit()
    return token


def accept_invite(db: Session, token: str, password: str) -> tuple[User, str]:
    """Set the password of an invited owner and log them in. Token is validated before the password policy."""
    claims = decode_token(db, token)  # decode_token can't tell token types apart; check below
    if claims.get("userType") != "invite":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    try:
        user = db.get(User, UUID(claims["sub"]))
    except (KeyError, ValueError):
        user = None
    if user is None or user.passwordHash is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired invite")
    validate_password_policy(password)
    user.passwordHash = hash_password(password)
    return user, refresh_and_store_user_token(db, user)  # commits the hash and the session iat together


def refresh_and_store_institution_token(db: Session, inst_user: InstitutionUser) -> str:
    token = issue_token(db, inst_user.id, "institution_user", institution_id=inst_user.institutionId)
    claims = decode_token(db, token)
    inst_user.lastTokenIssuedAt = datetime.fromtimestamp(claims["iat"], tz=UTC)
    db.commit()
    return token


def bootstrap_institution(
    db: Session,
    institution_name: str,
    officer_name: str,
    officer_email: str,
    officer_password: str,
) -> tuple[Institution, InstitutionUser, str]:
    validate_password_policy(officer_password)

    existing = db.query(InstitutionUser).filter(InstitutionUser.email == officer_email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    institution = Institution(name=institution_name)
    db.add(institution)
    db.flush()

    officer = InstitutionUser(
        institutionId=institution.id,
        name=officer_name,
        email=officer_email,
        role="loan_officer",
        passwordHash=hash_password(officer_password),
    )
    db.add(officer)
    db.flush()

    token = refresh_and_store_institution_token(db, officer)
    db.refresh(institution)
    db.refresh(officer)
    return institution, officer, token


def ensure_user_property_scope(db: Session, user_id: UUID, property_id: UUID) -> None:
    row = (
        db.query(UserProperty.id).filter(UserProperty.userId == user_id, UserProperty.propertyId == property_id).first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not enrolled on this property")


def ensure_institution_not_revoked(db: Session, institution_user_id: UUID) -> None:
    revoked = db.query(TokenRevocation.id).filter(TokenRevocation.institutionUserId == institution_user_id).first()
    if revoked is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Institution token revoked")
