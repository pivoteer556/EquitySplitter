import hmac
import re
from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, platform_admin_principal, require_institution_user
from app.api.routes.totp import TotpEnrollment
from app.core.config import settings
from app.db.session import get_db
from app.models import InstitutionUser, RecoveryCode, TokenRevocation, TotpCredential, User
from app.schemas.auth import (
    AcceptInviteRequest,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    EnrolConfirmRequest,
    EnrolConfirmResponse,
    EnrolmentChallenge,
    EnrolStartRequest,
    InstitutionBootstrapRequest,
    InstitutionBootstrapResponse,
    InstitutionRevokeRequest,
    LoginResponse,
    LoginTotpRequest,
    SecondFactorChallenge,
)
from app.schemas.institution import InstitutionRead, InstitutionUserRead
from app.services import auth as auth_service  # module access, so the test clock patch applies
from app.services import totp
from app.services.auth import (
    accept_invite,
    activate_institution_user,
    bootstrap_institution,
    burn_password_check,
    decode_token,
    hash_password,
    issue_login_challenge_token,
    now_utc_seconds,
    refresh_and_store_institution_token,
    refresh_and_store_user_token,
    validate_password_policy,
    verify_and_upgrade_password,
)
from app.services.rate_limit import RateLimiter, login_limiter, signup_limiter

router = APIRouter(prefix="/auth")

ENROLMENT_PURPOSE = "enrolment_challenge"  # token purpose; see issue_login_challenge_token


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


def _fail_login(db: Session, key: str, status_code: int, detail: str) -> NoReturn:
    login_limiter.record_attempt(db, key)
    raise HTTPException(status_code=status_code, detail=detail)


def _enforce_limit(limiter: RateLimiter, db: Session, key: str, detail: str) -> None:
    wait = limiter.retry_after(db, key)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(wait)},
        )


def _enforce_login_limit(db: Session, key: str) -> None:
    _enforce_limit(login_limiter, db, key, "Too many failed login attempts")


def _enforce_signup_limit(db: Session, request: Request, scope: str = "signup") -> None:
    # Every attempt counts (accepted or rejected): account creation itself is what is being throttled.
    # `scope` namespaces the key so endpoints (e.g. accept-invite) get their own per-IP budget.
    key = f"{scope}:{_client_ip(request)}"
    _enforce_limit(signup_limiter, db, key, "Too many signup attempts")
    signup_limiter.record_attempt(db, key)


@router.post("/institution/bootstrap", response_model=InstitutionBootstrapResponse, status_code=status.HTTP_201_CREATED)
def institution_bootstrap(
    payload: InstitutionBootstrapRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_bootstrap_token: str | None = Header(default=None),
):
    # Limit first and record the attempt, so guessing the token is throttled like any other signup.
    _enforce_signup_limit(db, request)
    expected = settings.bootstrap_token
    # Missing, wrong and disabled (no token configured) are deliberately indistinguishable: same 404, same body.
    # Bytes, because compare_digest rejects non-ASCII str.
    if not expected or not hmac.compare_digest((x_bootstrap_token or "").encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Second factor of the gate: a signed-in platform admin. Every failure (no/garbage/expired bearer, wrong account
    # kind) is the same 404 as a bad setup token. Checked after the token so only token holders touch sessions.
    try:
        # Authorization is read from the request (not a parameter) to stay within the argument-count lint.
        platform_admin_principal(response, db, request.headers.get("authorization"))
    except (HTTPException, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    institution, officer, token = bootstrap_institution(
        db,
        payload.institutionName,
        payload.officerName,
        payload.officerEmail,
    )
    return InstitutionBootstrapResponse(
        institution=InstitutionRead.model_validate(institution),
        institutionUser=InstitutionUserRead.model_validate(officer),
        activationToken=token,
        activationPath=f"/activate#token={token}",
    )


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_signup_limit(db, request)
    validate_password_policy(payload.password)
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        passwordHash=hash_password(payload.password),
        passwordSetAt=now_utc_seconds(),
    )
    db.add(user)
    db.flush()
    token = refresh_and_store_user_token(db, user)
    return AuthTokenResponse(accessToken=token)


def _authenticate(db: Session, email: str, password: str) -> User | InstitutionUser | None:
    """Try the user account first, then the officer account. Every miss spends one argon2 verification (a real one or
    a dummy), so a failure costs two whatever exists and does not reveal which kind of account an email is."""
    candidates: tuple[User | InstitutionUser | None, ...] = (
        db.query(User).filter(User.email == email).first(),
        db.query(InstitutionUser).filter(InstitutionUser.email == email).first(),
    )
    for account in candidates:
        if account is None or account.passwordHash is None:
            burn_password_check(password)
        elif verify_and_upgrade_password(db, account, password):
            return account
    return None


def _confirmed_credential(db: Session, officer_id: UUID) -> TotpCredential | None:
    return (
        db.query(TotpCredential)
        .filter(TotpCredential.institutionUserId == officer_id, TotpCredential.confirmedAt.is_not(None))
        .first()
    )


@router.post("/login", response_model=LoginResponse | SecondFactorChallenge | EnrolmentChallenge)
def login(payload: AuthLoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _login_key("login", request, payload.email)  # one budget per ip+email, whichever kind of account it is
    _enforce_login_limit(db, key)
    account = _authenticate(db, payload.email, payload.password)
    if account is None:
        _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")  # one failure counts once
    if isinstance(account, InstitutionUser) and _confirmed_credential(db, account.id) is not None:
        # Password proven, session not issued yet. The budget is NOT reset here: only a finished sign-in clears it,
        # so a stolen password cannot be used to keep wiping the counter while guessing codes.
        return SecondFactorChallenge(challengeToken=issue_login_challenge_token(db, account.id))
    if isinstance(account, InstitutionUser):
        # No authenticator yet: the password alone never signs an officer in. Same budget rule as above.
        return EnrolmentChallenge(challengeToken=issue_login_challenge_token(db, account.id, ENROLMENT_PURPOSE))
    login_limiter.reset(db, key)
    return LoginResponse(
        accessToken=refresh_and_store_user_token(db, account),
        userType="user",
        isPlatformAdmin=account.isPlatformAdmin,
    )


@router.post("/login/totp", response_model=LoginResponse)
def login_totp(payload: LoginTotpRequest, request: Request, db: Session = Depends(get_db)):
    """Second sign-in step. Every failure is the same 401 as a bad password and counts toward the same "login"
    budget (keyed by ip+email, so the password step and the code step share one limit)."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    officer = _officer_from_challenge(db, payload.challengeToken, "login_challenge")
    if officer is None:
        # A forged challenge is impossible (signed) so there is no email to charge; nothing to count against.
        raise invalid
    key = _login_key("login", request, officer.email)
    _enforce_login_limit(db, key)
    credential = _confirmed_credential(db, officer.id)
    if credential is not None and not re.fullmatch(r"\d{6}", payload.code):
        # Not six digits, so it can only be a recovery code. Same failure, same budget as a wrong authenticator code.
        if not _consume_recovery_code(db, officer.id, payload.code):
            _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        login_limiter.reset(db, key)
        return _officer_login_response(db, officer)
    step = None
    if credential is not None:
        step = totp.verify_code(
            totp.decrypt_secret(credential.secretEncrypted),
            payload.code,
            auth_service.now_utc_seconds(),
            credential.lastUsedStep,
        )
    if credential is None or step is None:
        _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    credential.lastUsedStep = step  # single use: the same or an older code is a replay next time
    login_limiter.reset(db, key)
    return _officer_login_response(db, officer)  # commits lastUsedStep with the session iat


def _consume_recovery_code(db: Session, officer_id: UUID, code: str) -> bool:
    """Spend the officer's matching unused recovery code. Compares against every unused row with no early exit, and the
    spend is a conditional UPDATE so two concurrent requests cannot both redeem one code. Not committed here:
    _officer_login_response commits it together with the session."""
    wanted = totp.hash_recovery_code(code)
    unused = (RecoveryCode.institutionUserId == officer_id, RecoveryCode.usedAt.is_(None))
    rows = db.query(RecoveryCode).filter(*unused).all()
    match = None
    for row in rows:
        if hmac.compare_digest(row.codeHash, wanted):
            match = row
    if match is None:
        return False
    spent = (
        db.query(RecoveryCode)
        .filter(RecoveryCode.id == match.id, RecoveryCode.usedAt.is_(None))
        .update({RecoveryCode.usedAt: datetime.now(UTC)}, synchronize_session=False)
    )
    return spent == 1


def _officer_from_challenge(db: Session, token: str, purpose: str) -> InstitutionUser | None:
    """The officer a challenge token names, or None for anything else. decode_token cannot tell token types apart,
    so the purpose is checked here: an access token or the other kind of challenge must not pass."""
    try:
        claims = decode_token(db, token)
    except HTTPException:
        return None
    if claims.get("userType") != purpose:
        return None
    try:
        return db.get(InstitutionUser, UUID(claims["sub"]))
    except (KeyError, ValueError):
        return None


def _officer_login_response(db: Session, officer: InstitutionUser) -> LoginResponse:
    return LoginResponse(
        accessToken=refresh_and_store_institution_token(db, officer),
        userType="institution_user",
        isPlatformAdmin=False,
        role=officer.role,
        institutionId=officer.institutionId,
    )


@router.post("/login/totp/enroll-start", response_model=TotpEnrollment)
def login_totp_enroll_start(payload: EnrolStartRequest, request: Request, db: Session = Depends(get_db)):
    """First sign-in, step 2a: start (or restart, until confirmed) enrolment with the enrolment challenge instead of a
    bearer. An already-enrolled officer, or any other token, gets the generic 401."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    officer = _officer_from_challenge(db, payload.challengeToken, ENROLMENT_PURPOSE)
    if officer is None or _confirmed_credential(db, officer.id) is not None:
        raise invalid
    _enforce_login_limit(db, _login_key("login", request, officer.email))
    secret = totp.new_secret()
    credential = db.query(TotpCredential).filter(TotpCredential.institutionUserId == officer.id).first()
    if credential is None:
        db.add(TotpCredential(institutionUserId=officer.id, secretEncrypted=totp.encrypt_secret(secret)))
    else:
        credential.secretEncrypted = totp.encrypt_secret(secret)  # replaces the pending (unconfirmed) one
    db.commit()
    return TotpEnrollment(secret=secret, otpauthUri=totp.provisioning_uri(secret, officer.email))


@router.post("/login/totp/enroll-confirm", response_model=EnrolConfirmResponse)
def login_totp_enroll_confirm(payload: EnrolConfirmRequest, request: Request, db: Session = Depends(get_db)):
    """First sign-in, step 2b: prove the authenticator works. Failures are the generic 401 and count toward the shared
    "login" budget, exactly like a wrong code at /login/totp."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    officer = _officer_from_challenge(db, payload.challengeToken, ENROLMENT_PURPOSE)
    if officer is None:
        raise invalid
    key = _login_key("login", request, officer.email)
    _enforce_login_limit(db, key)
    credential = db.query(TotpCredential).filter(TotpCredential.institutionUserId == officer.id).first()
    step = None
    if credential is not None and credential.confirmedAt is None:  # confirmed officers cannot re-enrol this way
        secret = totp.decrypt_secret(credential.secretEncrypted)
        step = totp.verify_code(secret, payload.code, auth_service.now_utc_seconds(), None)
    if credential is None or step is None:
        _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    credential.confirmedAt = datetime.now(UTC)
    credential.lastUsedStep = step
    login_limiter.reset(db, key)
    codes = [totp.new_recovery_code() for _ in range(totp.RECOVERY_CODE_COUNT)]
    db.add_all(RecoveryCode(institutionUserId=officer.id, codeHash=totp.hash_recovery_code(c)) for c in codes)
    base = _officer_login_response(db, officer)  # commits the credential and codes with the session iat
    return EnrolConfirmResponse(**base.model_dump(), recoveryCodes=codes)


@router.post("/accept-invite", response_model=AuthTokenResponse)
def accept_invite_route(payload: AcceptInviteRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_signup_limit(db, request, scope="accept-invite")
    _, token = accept_invite(db, payload.token, payload.password)
    return AuthTokenResponse(accessToken=token)


@router.post("/institution/activate", response_model=AuthTokenResponse)
def institution_activate(payload: AcceptInviteRequest, request: Request, db: Session = Depends(get_db)):
    _enforce_signup_limit(db, request, scope="institution-activate")
    _, token = activate_institution_user(db, payload.token, payload.password)
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
    target.lastTokenIssuedAt = datetime.now(UTC).replace(microsecond=0)
    db.add(revocation)
    db.commit()
    return None
