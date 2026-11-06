import hashlib

from app.models import User
from app.services.auth import hash_password, verify_and_upgrade_password


def _legacy_user(db, password: str) -> User:
    salt = "abc123"
    user = User(
        name="Legacy",
        email="legacy@example.com",
        passwordSalt=salt,
        passwordHash=hashlib.sha256(f"{salt}:{password}".encode()).hexdigest(),
    )
    db.add(user)
    db.commit()
    return user


def test_hash_is_argon2id_and_salted():
    first, second = hash_password("ValidPass123!"), hash_password("ValidPass123!")
    assert first.startswith("$argon2id$")
    assert first != second  # per-hash random salt


def test_legacy_sha256_hash_verifies_and_is_upgraded(session_factory):
    db = session_factory()
    user = _legacy_user(db, "ValidPass123!")

    assert verify_and_upgrade_password(db, user, "ValidPass123!") is True

    db.refresh(user)
    assert user.passwordHash.startswith("$argon2id$")
    assert user.passwordSalt is None
    assert verify_and_upgrade_password(db, user, "ValidPass123!") is True
    db.close()


def test_legacy_hash_wrong_password_is_not_upgraded(session_factory):
    db = session_factory()
    user = _legacy_user(db, "ValidPass123!")
    original = user.passwordHash

    assert verify_and_upgrade_password(db, user, "WrongPass123!") is False
    assert user.passwordHash == original
    db.close()


def test_missing_hash_never_verifies(session_factory):
    db = session_factory()
    user = User(name="Invited", email="invited@example.com")
    db.add(user)
    db.commit()
    assert verify_and_upgrade_password(db, user, "anything") is False
    db.close()
