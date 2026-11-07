from datetime import UTC, datetime, timedelta

import jwt

from tests.conftest import STRONG_PASSWORD, bearer
from tests.test_property_flow import _agreement, _property

API = "/api/v1"
NEW_PASSWORD = "BrandNew456!"


def _invite(client, officer, prop_id, email="owner@example.com"):
    return client.post(
        f"{API}/properties/{prop_id}/owners",
        json={"name": "Owner", "email": email},
        headers=bearer(officer["accessToken"]),
    )


def _invited(client, officer, email="owner@example.com"):
    prop = _property(client, officer)
    assert _agreement(client, officer, prop["id"]).status_code == 201
    resp = _invite(client, officer, prop["id"], email)
    assert resp.status_code == 201, resp.text
    return prop, resp.json()["inviteToken"]


def _accept(client, token, password=NEW_PASSWORD):
    return client.post(f"{API}/auth/accept-invite", json={"token": token, "password": password})


def _user_id(session_factory, email="owner@example.com"):
    from app.models import User

    db = session_factory()
    try:
        return db.query(User).filter(User.email == email).one().id
    finally:
        db.close()


def _signed(session_factory, claims):
    from app.services.auth import ensure_secret_state

    db = session_factory()
    try:
        return jwt.encode(claims, ensure_secret_state(db).currentSecret, algorithm="HS256")
    finally:
        db.close()


def test_accept_invite_sets_password_and_allows_login(client, officer):
    prop, token = _invited(client, officer)
    # Before accepting, login is refused exactly as before.
    assert (
        client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": NEW_PASSWORD}).status_code
        == 403
    )

    resp = _accept(client, token)
    assert resp.status_code == 200, resp.text
    assert resp.json()["tokenType"] == "Bearer"
    # The returned token is a normal access token.
    ack = client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(resp.json()["accessToken"]))
    assert ack.status_code == 200

    login = client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": NEW_PASSWORD})
    assert login.status_code == 200
    assert (
        client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": "WrongPass123!"}).status_code
        == 401
    )


def test_invite_token_is_single_use(client, officer):
    _, token = _invited(client, officer)
    assert _accept(client, token).status_code == 200
    again = _accept(client, token, "Another789!x")
    assert again.status_code == 401
    # The first password still stands; the second attempt did not overwrite it.
    assert (
        client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": NEW_PASSWORD}).status_code
        == 200
    )


def test_expired_invite_token_is_rejected(client, officer, session_factory):
    _invited(client, officer)
    uid = _user_id(session_factory)
    past = datetime.now(UTC) - timedelta(days=1)
    expired = _signed(
        session_factory,
        {
            "sub": str(uid),
            "userType": "invite",
            "iat": int((past - timedelta(days=7)).timestamp()),
            "exp": int(past.timestamp()),
        },
    )
    assert _accept(client, expired).status_code == 401


def test_access_token_is_not_an_invite_token(client, officer, session_factory):
    from app.services.auth import issue_token

    _invited(client, officer)
    uid = _user_id(session_factory)
    db = session_factory()
    access = issue_token(db, uid, "user")  # same subject, valid signature: only the userType can reject it
    db.close()
    assert _accept(client, access).status_code == 401
    assert (
        client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": NEW_PASSWORD}).status_code
        == 403
    )


def test_garbage_token_is_rejected(client, officer):
    assert _accept(client, "not-a-jwt").status_code == 401


def test_invite_token_is_not_an_access_token(client, officer):
    prop, token = _invited(client, officer)
    # Existing deps reject a wrong userType with 403 "Wrong identity type for endpoint".
    assert client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(token)).status_code == 403
    assert client.get(f"{API}/properties/{prop['id']}", headers=bearer(token)).status_code == 403
    assert client.post(f"{API}/auth/institution/revoke", json={}, headers=bearer(token)).status_code == 403


def test_weak_password_is_rejected_and_token_stays_usable(client, officer, session_factory):
    from app.models import User

    _, token = _invited(client, officer)
    assert _accept(client, token, "weak").status_code == 400
    db = session_factory()
    assert db.query(User).filter(User.email == "owner@example.com").one().passwordHash is None
    db.close()
    assert _accept(client, token).status_code == 200


def test_invite_token_only_for_passwordless_invitee(client, officer):
    # A registered user already has a password: inviting them returns no token.
    client.post(f"{API}/auth/register", json={"name": "Reg", "email": "reg@example.com", "password": STRONG_PASSWORD})
    prop = _property(client, officer)
    assert _agreement(client, officer, prop["id"]).status_code == 201
    resp = _invite(client, officer, prop["id"], "reg@example.com")
    assert resp.status_code == 201
    assert resp.json().get("inviteToken") is None

    # A passwordless invitee gets one, and re-inviting (idempotent path) still returns a token.
    fresh = _invite(client, officer, prop["id"], "fresh@example.com")
    assert fresh.json()["inviteToken"]
    again = _invite(client, officer, prop["id"], "fresh@example.com")
    assert again.json()["id"] == fresh.json()["id"]
    assert again.json()["inviteToken"]

    # Once the password is set, a re-invite no longer hands out a token.
    assert _accept(client, fresh.json()["inviteToken"]).status_code == 200
    assert _invite(client, officer, prop["id"], "fresh@example.com").json().get("inviteToken") is None
