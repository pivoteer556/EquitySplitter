"""Authenticator-app (TOTP, RFC 6238) helpers. Secrets are encrypted at rest with a key derived from
JWT_SECRET_SEED; changing that seed makes stored secrets unreadable (everyone would have to re-enrol)."""

import base64
import hmac

import pyotp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

ISSUER = "EquitySplitter"
STEP_SECONDS = 30
WINDOW_STEPS = 1  # accept the previous, current and next step (clock drift)


def _fernet() -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"equitysplitter-totp-secret-v1").derive(
        settings.jwt_secret_seed.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(key))


def new_secret() -> str:
    return pyotp.random_base32(length=32)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("ascii")


def provisioning_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret, interval=STEP_SECONDS).provisioning_uri(name=account, issuer_name=ISSUER)


def verify_code(secret: str, code: str, now, last_used_step: int | None) -> int | None:
    """Return the accepted time step, or None. A step at or before last_used_step is a replay and is refused."""
    totp = pyotp.TOTP(secret, interval=STEP_SECONDS)
    current = int(now.timestamp()) // STEP_SECONDS
    accepted: int | None = None
    for step in range(current - WINDOW_STEPS, current + WINDOW_STEPS + 1):  # no early exit: constant work
        match = hmac.compare_digest(totp.at(step * STEP_SECONDS), code)
        if match and (last_used_step is None or step > last_used_step) and (accepted is None or step > accepted):
            accepted = step
    return accepted
