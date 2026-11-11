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
from app.schemas.types import normalize_email

PASSWORD_POLICY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$")

INVITE_TOKEN_DAYS = 7
LOGIN_CHALLENGE_MINUTES = 5


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


def unusable_password_hash() -> str:
    """A valid argon2 hash of a random secret that is discarded: no password can ever verify against it."""
    return _hasher.hash(secrets.token_urlsafe(32))


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
    (passwordSetAt must still be unset)."""
    iat_dt = now_utc_seconds()
    claims = {
        "sub": str(user_id),
        "userType": "invite",
        "iat": int(iat_dt.timestamp()),
        "exp": int((iat_dt + timedelta(days=INVITE_TOKEN_DAYS)).timestamp()),
    }
    return jwt.encode(claims, ensure_secret_state(db).currentSecret, algorithm="HS256")


def issue_institution_invite_token(db: Session, institution_user_id: UUID) -> str:
    """Like issue_invite_token, for an officer's one-time activation link. userType="institution_invite" keeps it out
    of every auth dependency. Single-use is enforced by activate_institution_user (passwordSetAt must be unset)."""
    iat_dt = now_utc_seconds()
    claims = {
        "sub": str(institution_user_id),
        "userType": "institution_invite",
        "iat": int(iat_dt.timestamp()),
        "exp": int((iat_dt + timedelta(days=INVITE_TOKEN_DAYS)).timestamp()),
    }
    return jwt.encode(claims, ensure_secret_state(db).currentSecret, algorithm="HS256")


def issue_login_challenge_token(db: Session, institution_user_id: UUID, purpose: str = "login_challenge") -> str:
    """Stateless proof that the password step passed, redeemable only at POST /auth/login/totp. userType=
    "login_challenge" keeps it out of every auth dependency (they accept only user/institution_user). It is not
    single-use by itself: the one-time TOTP code is what cannot be replayed, and wrong codes are rate limited.
    `purpose` "enrolment_challenge" is the same proof for an officer with no authenticator yet; the two purposes are
    not interchangeable (each endpoint checks its own)."""
    iat_dt = now_utc_seconds()
    claims = {
        "sub": str(institution_user_id),
        "userType": purpose,
        "iat": int(iat_dt.timestamp()),
        "exp": int((iat_dt + timedelta(minutes=LOGIN_CHALLENGE_MINUTES)).timestamp()),
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
    if user is None or user.passwordSetAt is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired invite")
    validate_password_policy(password)
    user.passwordHash = hash_password(password)
    user.passwordSetAt = now_utc_seconds()
    return user, refresh_and_store_user_token(db, user)  # commits the hash and the session iat together


def create_platform_admin(db: Session, email: str) -> str:
    """Operator-only (no endpoint calls this). Create a password-less platform admin, or re-issue the link for an
    existing one, and return a one-time set-password token from the SAME generator as owner invites
    (issue_invite_token, redeemed at accept-invite). Never sets or changes a password; refuses to promote an
    ordinary account."""
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            name="Platform Admin",
            email=email,
            passwordHash=unusable_password_hash(),
            passwordSetAt=None,
            isPlatformAdmin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.isPlatformAdmin:
        raise ValueError("An ordinary account with this email already exists; it will not be promoted")
    return issue_invite_token(db, user.id)


def refresh_and_store_institution_token(db: Session, inst_user: InstitutionUser) -> str:
    token = issue_token(db, inst_user.id, "institution_user", institution_id=inst_user.institutionId)
    claims = decode_token(db, token)
    inst_user.lastTokenIssuedAt = datetime.fromtimestamp(claims["iat"], tz=UTC)
    db.commit()
    return token


def activate_institution_user(db: Session, token: str, password: str) -> tuple[InstitutionUser, str]:
    """Set the password of a not-yet-activated officer and log them in. Mirrors accept_invite."""
    claims = decode_token(db, token)
    if claims.get("userType") != "institution_invite":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    try:
        officer = db.get(InstitutionUser, UUID(claims["sub"]))
    except (KeyError, ValueError):
        officer = None
    if officer is None or officer.passwordSetAt is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired invite")
    validate_password_policy(password)
    officer.passwordHash = hash_password(password)
    officer.passwordSetAt = now_utc_seconds()
    return officer, refresh_and_store_institution_token(db, officer)  # commits the hash and the session iat together


EMAIL_TAKEN = "Email already registered"  # same detail as /auth/register


def ensure_officer_email_free(db: Session, email: str) -> None:
    """409 if an officer already has this email. institutionUsers.email is UNIQUE across all institutions (exact
    match, like the column); buyers live in `users` and do not count. Callers also catch IntegrityError on commit
    (a lost race), because this check is not atomic with the insert."""
    if db.query(InstitutionUser.id).filter(InstitutionUser.email == email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)


def bootstrap_institution(
    db: Session,
    institution_name: str,
    officer_name: str,
    officer_email: str,
) -> tuple[Institution, InstitutionUser, str]:
    """Create an institution and its first officer, who has no password until they activate. Returns the one-time
    activation token (no session exists before activation)."""
    ensure_officer_email_free(db, officer_email)

    institution = Institution(name=institution_name)
    db.add(institution)
    db.flush()

    officer = InstitutionUser(
        institutionId=institution.id,
        name=officer_name,
        email=officer_email,
        role="loan_officer",
        passwordHash=unusable_password_hash(),
        passwordSetAt=None,
    )
    db.add(officer)
    db.commit()  # nothing below commits (refresh_and_store_institution_token used to)

    token = issue_institution_invite_token(db, officer.id)
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
