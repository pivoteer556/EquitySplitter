"""Authenticator-app (TOTP, RFC 6238) helpers. Secrets are encrypted at rest with a key derived from
JWT_SECRET_SEED; changing that seed makes stored secrets unreadable (everyone would have to re-enrol)."""

import base64
import hmac
import secrets

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


RECOVERY_CODE_COUNT = 8
# 31 characters with no 0/O/1/I/L lookalikes; 10 of them is ~49.5 bits, ample for a single-use code behind a limiter.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
RECOVERY_LENGTH = 10


def new_recovery_code() -> str:
    """Display form, e.g. "K7M2Q-X9RPA": two groups of five."""
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(RECOVERY_LENGTH))
    return f"{raw[:5]}-{raw[5:]}"


def normalize_recovery_code(code: str) -> str:
    """Case, whitespace and dashes do not matter: "k7m2q x9rpa" is "K7M2QX9RPA"."""
    return "".join(ch for ch in code.upper() if ch in _RECOVERY_ALPHABET)


def hash_recovery_code(code: str) -> str:
    """HMAC-SHA256 keyed from JWT_SECRET_SEED (own HKDF label, so the key is not shared with the TOTP encryption). The
    codes are random 50-bit values, so a fast keyed hash is enough (no password-style stretching needed), and the key
    means a leaked table cannot be brute-forced offline without the app secret."""
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"equitysplitter-recovery-code-v1").derive(
        settings.jwt_secret_seed.encode("utf-8")
    )
    return hmac.new(key, normalize_recovery_code(code).encode("ascii"), "sha256").hexdigest()


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
