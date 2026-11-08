from app.models import User
from tests.conftest import STRONG_PASSWORD
from tests.test_accept_invite import API, NEW_PASSWORD, _accept, _invited


def _row(session_factory, email):
    db = session_factory()
    try:
        row = db.query(User).filter(User.email == email).one()
        db.expunge(row)
        return row
    finally:
        db.close()


def test_invited_user_has_unusable_hash_and_no_password_set_marker(client, officer, session_factory):
    _invited(client, officer)
    row = _row(session_factory, "owner@example.com")
    assert row.passwordHash is not None
    assert row.passwordHash.startswith("$argon2")
    assert row.passwordSetAt is None


def test_accept_sets_marker_and_second_accept_is_rejected(client, officer, session_factory):
    _, token = _invited(client, officer)
    assert _accept(client, token).status_code == 200
    assert _row(session_factory, "owner@example.com").passwordSetAt is not None

    again = _accept(client, token, "AnotherPass789!")
    assert again.status_code == 401
    assert again.json() == {"detail": "Invalid or expired invite"}


def test_invited_user_cannot_log_in_with_any_password(client, officer):
    _invited(client, officer)
    for guess in ("a", " ", NEW_PASSWORD, STRONG_PASSWORD, "$argon2id$v=19$m=65536,t=3,p=4$x$y"):
        resp = client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": guess})
        assert resp.status_code == 401, guess
        assert resp.json() == {"detail": "Invalid credentials"}


def test_registered_user_has_password_set_marker(client, session_factory):
    client.post(f"{API}/auth/register", json={"name": "Reg", "email": "reg@example.com", "password": STRONG_PASSWORD})
    assert _row(session_factory, "reg@example.com").passwordSetAt is not None
