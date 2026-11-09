from tests.conftest import BOOTSTRAP_HEADERS, STRONG_PASSWORD, bearer

BOOTSTRAP = "/api/v1/auth/institution/bootstrap"
LOGIN = "/api/v1/auth/institution/login"
ACTIVATE = "/api/v1/auth/institution/activate"


def _bootstrap_body(**extra):
    base = {"institutionName": "Atlas Lending", "officerName": "Casey Officer", "officerEmail": "casey@example.com"}
    return {**base, **extra}


def test_bootstrap_returns_activation_link_and_no_session(client, platform_admin):
    resp = client.post(BOOTSTRAP, json=_bootstrap_body(), headers={**platform_admin, **BOOTSTRAP_HEADERS})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["activationPath"] == f"/activate#token={body['activationToken']}"
    assert body["institutionUser"]["institutionId"] == body["institution"]["id"]
    assert body["institutionUser"]["role"] == "loan_officer"
    assert "accessToken" not in body and "tokenType" not in body
    assert "passwordHash" not in resp.text and "password" not in body["institutionUser"]


def test_bootstrap_officer_cannot_log_in_until_activated(client, session_factory, platform_admin):
    from app.models import InstitutionUser

    body = client.post(BOOTSTRAP, json=_bootstrap_body(), headers={**platform_admin, **BOOTSTRAP_HEADERS}).json()
    db = session_factory()
    row = db.query(InstitutionUser).one()
    assert row.passwordSetAt is None
    db.close()
    login = {"email": "casey@example.com", "password": STRONG_PASSWORD}
    assert client.post(LOGIN, json=login).status_code == 401
    activate = {"token": body["activationToken"], "password": STRONG_PASSWORD}
    assert client.post(ACTIVATE, json=activate).status_code == 200
    assert client.post(LOGIN, json=login).status_code == 200
    db = session_factory()
    row = db.query(InstitutionUser).one()
    assert row.passwordSetAt is not None
    assert row.passwordHash.startswith("$argon2id$")
    db.close()


def test_bootstrap_rejects_a_sent_password(client, platform_admin):
    resp = client.post(
        BOOTSTRAP,
        json=_bootstrap_body(officerPassword=STRONG_PASSWORD),
        headers={**platform_admin, **BOOTSTRAP_HEADERS},
    )
    assert resp.status_code == 422


def test_bootstrap_rejects_duplicate_email(client, officer, platform_admin):
    resp = client.post(
        BOOTSTRAP,
        json=_bootstrap_body(institutionName="Other"),
        headers={**platform_admin, **BOOTSTRAP_HEADERS},
    )
    assert resp.status_code == 409


def test_register_and_login(client):
    reg = client.post(
        "/api/v1/auth/register", json={"name": "Sam", "email": "Sam@Example.com", "password": STRONG_PASSWORD}
    )
    assert reg.status_code == 201
    ok = client.post("/api/v1/auth/login", json={"email": "sam@example.com", "password": STRONG_PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["tokenType"] == "Bearer"
    bad = client.post("/api/v1/auth/login", json={"email": "sam@example.com", "password": "WrongPass123!"})
    assert bad.status_code == 401


def test_register_rejects_weak_password_and_duplicate(client):
    assert (
        client.post(
            "/api/v1/auth/register", json={"name": "A", "email": "a@example.com", "password": "short"}
        ).status_code
        == 400
    )
    body = {"name": "A", "email": "a@example.com", "password": STRONG_PASSWORD}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409


def test_login_unknown_account_is_generic_failure(client):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": STRONG_PASSWORD})
    assert resp.status_code == 401


def test_institution_login(client, officer):
    ok = client.post("/api/v1/auth/institution/login", json={"email": "casey@example.com", "password": STRONG_PASSWORD})
    assert ok.status_code == 200
    bad = client.post(
        "/api/v1/auth/institution/login", json={"email": "casey@example.com", "password": "WrongPass123!"}
    )
    assert bad.status_code == 401


def test_protected_route_requires_valid_bearer_token(client):
    assert client.post("/api/v1/institutions", json={"name": "X"}).status_code == 401
    assert client.post("/api/v1/institutions", json={"name": "X"}, headers=bearer("garbage")).status_code == 401


def test_user_token_rejected_on_institution_endpoint(client):
    token = client.post(
        "/api/v1/auth/register", json={"name": "U", "email": "u@example.com", "password": STRONG_PASSWORD}
    ).json()["accessToken"]
    assert client.post("/api/v1/institutions", json={"name": "X"}, headers=bearer(token)).status_code == 403


def test_authenticated_call_returns_refreshed_token(client, officer):
    resp = client.post("/api/v1/institutions", json={"name": "Second"}, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 201
    assert "X-Refreshed-Token" in resp.headers


def test_token_is_superseded_by_the_refreshed_one(client, officer, clock):
    from datetime import timedelta

    old = officer["accessToken"]
    clock["now"] += timedelta(seconds=1)
    first = client.post("/api/v1/institutions", json={"name": "A"}, headers=bearer(old))
    assert first.status_code == 201
    # The first call rotated the stored iat, so the original token no longer matches.
    assert client.post("/api/v1/institutions", json={"name": "B"}, headers=bearer(old)).status_code == 401
    assert (
        client.post(
            "/api/v1/institutions", json={"name": "B"}, headers=bearer(first.headers["X-Refreshed-Token"])
        ).status_code
        == 201
    )


def test_revoked_institution_user_is_locked_out(client, officer):
    token = officer["accessToken"]
    assert client.post("/api/v1/auth/institution/revoke", json={}, headers=bearer(token)).status_code == 204
    assert client.post("/api/v1/institutions", json={"name": "X"}, headers=bearer(token)).status_code == 401


def test_cannot_revoke_other_institution_user(client, officer):
    other = "00000000-0000-0000-0000-000000000001"
    resp = client.post(
        "/api/v1/auth/institution/revoke", json={"institutionUserId": other}, headers=bearer(officer["accessToken"])
    )
    assert resp.status_code == 403
