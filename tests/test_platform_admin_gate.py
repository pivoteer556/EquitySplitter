import jwt

from tests.conftest import BOOTSTRAP_HEADERS, STRONG_PASSWORD, bearer

URL = "/api/v1/auth/institution/bootstrap"
BODY = {"institutionName": "Gate Co", "officerName": "Gail", "officerEmail": "gail@example.com"}
NOT_FOUND = (404, {"detail": "Not found"})


def _post(client, headers=None):
    resp = client.post(URL, json=BODY, headers=headers)
    return resp.status_code, resp.json()


def test_token_without_session_rejected(client):
    assert _post(client, BOOTSTRAP_HEADERS) == NOT_FOUND


def test_session_without_token_rejected(client, platform_admin):
    assert _post(client, platform_admin) == NOT_FOUND


def test_platform_admin_with_token_succeeds(client, platform_admin):
    resp = client.post(URL, json=BODY, headers={**platform_admin, **BOOTSTRAP_HEADERS})
    assert resp.status_code == 201, resp.text
    assert resp.json()["activationToken"]


def test_garbage_and_expired_bearer_rejected(client, platform_admin, clock):
    assert _post(client, {**bearer("garbage"), **BOOTSTRAP_HEADERS}) == NOT_FOUND
    assert _post(client, {"Authorization": "Basic abc", **BOOTSTRAP_HEADERS}) == NOT_FOUND
    expired = jwt.encode({"sub": "x", "userType": "user", "iat": 1, "exp": 2}, "k", algorithm="HS256")
    assert _post(client, {**bearer(expired), **BOOTSTRAP_HEADERS}) == NOT_FOUND


def test_officer_session_with_token_rejected(client, platform_admin):
    made = client.post(URL, json=BODY, headers={**platform_admin, **BOOTSTRAP_HEADERS})
    assert made.status_code == 201, made.text
    activated = client.post(
        "/api/v1/auth/institution/activate", json={"token": made.json()["activationToken"], "password": STRONG_PASSWORD}
    )
    assert activated.status_code == 200, activated.text
    officer = bearer(activated.json()["accessToken"])
    assert _post(client, {**officer, **BOOTSTRAP_HEADERS}) == NOT_FOUND


def test_owner_and_buyer_sessions_with_token_rejected(client):
    reg = client.post(
        "/api/v1/auth/register", json={"name": "Bea Buyer", "email": "bea@example.com", "password": STRONG_PASSWORD}
    )
    assert reg.status_code == 201, reg.text
    assert _post(client, {**bearer(reg.json()["accessToken"]), **BOOTSTRAP_HEADERS}) == NOT_FOUND


def test_failed_attempt_does_not_rotate_admin_session(client, platform_admin):
    assert _post(client, platform_admin) == NOT_FOUND  # no setup token
    assert client.post(URL, json=BODY, headers={**platform_admin, **BOOTSTRAP_HEADERS}).status_code == 201


def test_rejections_create_nothing(client, session_factory):
    from app.models import Institution

    _post(client, BOOTSTRAP_HEADERS)
    with session_factory() as db:
        assert db.query(Institution).count() == 0


def test_register_cannot_make_a_platform_admin(client, session_factory):
    from app.models import User

    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Eve", "email": "eve@example.com", "password": STRONG_PASSWORD, "isPlatformAdmin": True},
    )
    assert resp.status_code in (201, 422)
    with session_factory() as db:
        user = db.query(User).filter(User.email == "eve@example.com").first()
        assert user is None or user.isPlatformAdmin is False

