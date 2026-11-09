import hmac
from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, platform_admin_principal, require_institution_user
from app.core.config import settings
from app.db.session import get_db
from app.models import InstitutionUser, TokenRevocation, TotpCredential, User
from app.schemas.auth import (
    AcceptInviteRequest,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    InstitutionBootstrapRequest,
    InstitutionBootstrapResponse,
    InstitutionRevokeRequest,
    LoginResponse,
    LoginTotpRequest,
    SecondFactorChallenge,
)
from app.schemas.institution import InstitutionRead, InstitutionUserRead
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


@router.post("/login", response_model=LoginResponse | SecondFactorChallenge)
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
    login_limiter.reset(db, key)
    if isinstance(account, InstitutionUser):
        return LoginResponse(
            accessToken=refresh_and_store_institution_token(db, account),
            userType="institution_user",
            isPlatformAdmin=False,
            role=account.role,
            institutionId=account.institutionId,
        )
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
    try:
        claims = decode_token(db, payload.challengeToken)
    except HTTPException:
        raise invalid from None
    # decode_token cannot tell token types apart: an access token must not pass as a challenge.
    officer = None
    if claims.get("userType") == "login_challenge":
        try:
            officer = db.get(InstitutionUser, UUID(claims["sub"]))
        except (KeyError, ValueError):
            officer = None
    if officer is None:
        # A forged challenge is impossible (signed) so there is no email to charge; nothing to count against.
        raise invalid
    key = _login_key("login", request, officer.email)
    _enforce_login_limit(db, key)
    credential = _confirmed_credential(db, officer.id)
    step = None
    if credential is not None:
        step = totp.verify_code(
            totp.decrypt_secret(credential.secretEncrypted), payload.code, now_utc_seconds(), credential.lastUsedStep
        )
    if credential is None or step is None:
        _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    credential.lastUsedStep = step  # single use: the same or an older code is a replay next time
    login_limiter.reset(db, key)
    return LoginResponse(
        accessToken=refresh_and_store_institution_token(db, officer),  # commits lastUsedStep with the session iat
        userType="institution_user",
        isPlatformAdmin=False,
        role=officer.role,
        institutionId=officer.institutionId,
    )


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


@router.post("/institution/login", response_model=AuthTokenResponse)
def institution_login(payload: AuthLoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _login_key("login", request, payload.email)  # shared with /login so the two cannot double the budget
    _enforce_login_limit(db, key)
    inst_user = db.query(InstitutionUser).filter(InstitutionUser.email == payload.email).first()
    if inst_user is None or inst_user.passwordHash is None:
        burn_password_check(payload.password)
        _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not verify_and_upgrade_password(db, inst_user, payload.password):
        _fail_login(db, key, status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    login_limiter.reset(db, key)
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
    target.lastTokenIssuedAt = datetime.now(UTC).replace(microsecond=0)
    db.add(revocation)
    db.commit()
    return None
