from tests.conftest import STRONG_PASSWORD, bearer


def test_bootstrap_stores_argon2_hash(client, session_factory, officer):
    from app.models import InstitutionUser

    db = session_factory()
    row = db.query(InstitutionUser).one()
    assert row.passwordHash.startswith("$argon2id$")
    assert row.passwordSalt is None
    db.close()


def test_bootstrap_rejects_weak_password(client):
    resp = client.post(
        "/api/v1/auth/institution/bootstrap",
        json={"institutionName": "X", "officerName": "Y", "officerEmail": "y@example.com", "officerPassword": "weak"},
    )
    assert resp.status_code == 400


def test_bootstrap_rejects_duplicate_email(client, officer):
    resp = client.post(
        "/api/v1/auth/institution/bootstrap",
        json={"institutionName": "Other", "officerName": "Dup", "officerEmail": "casey@example.com", "officerPassword": STRONG_PASSWORD},
    )
    assert resp.status_code == 409


def test_register_and_login(client):
    reg = client.post("/api/v1/auth/register", json={"name": "Sam", "email": "Sam@Example.com", "password": STRONG_PASSWORD})
    assert reg.status_code == 201
    ok = client.post("/api/v1/auth/login", json={"email": "sam@example.com", "password": STRONG_PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["tokenType"] == "Bearer"
    bad = client.post("/api/v1/auth/login", json={"email": "sam@example.com", "password": "WrongPass123!"})
    assert bad.status_code == 401


def test_register_rejects_weak_password_and_duplicate(client):
    assert client.post("/api/v1/auth/register", json={"name": "A", "email": "a@example.com", "password": "short"}).status_code == 400
    body = {"name": "A", "email": "a@example.com", "password": STRONG_PASSWORD}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409


def test_login_unknown_account_requires_reset(client):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": STRONG_PASSWORD})
    assert resp.status_code == 403


def test_institution_login(client, officer):
    ok = client.post("/api/v1/auth/institution/login", json={"email": "casey@example.com", "password": STRONG_PASSWORD})
    assert ok.status_code == 200
    bad = client.post("/api/v1/auth/institution/login", json={"email": "casey@example.com", "password": "WrongPass123!"})
    assert bad.status_code == 401


def test_protected_route_requires_valid_bearer_token(client):
    assert client.post("/api/v1/institutions", json={"name": "X"}).status_code == 401
    assert client.post("/api/v1/institutions", json={"name": "X"}, headers=bearer("garbage")).status_code == 401


def test_user_token_rejected_on_institution_endpoint(client):
    token = client.post("/api/v1/auth/register", json={"name": "U", "email": "u@example.com", "password": STRONG_PASSWORD}).json()["accessToken"]
    assert client.post("/api/v1/institutions", json={"name": "X"}, headers=bearer(token)).status_code == 403


def test_authenticated_call_returns_refreshed_token(client, officer):
    resp = client.post("/api/v1/institutions", json={"name": "Second"}, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 201
    assert "X-Refreshed-Token" in resp.headers


def test_revoked_institution_user_is_locked_out(client, officer):
    token = officer["accessToken"]
    assert client.post("/api/v1/auth/institution/revoke", json={}, headers=bearer(token)).status_code == 204
    assert client.post("/api/v1/institutions", json={"name": "X"}, headers=bearer(token)).status_code == 401


def test_cannot_revoke_other_institution_user(client, officer):
    other = "00000000-0000-0000-0000-000000000001"
    resp = client.post("/api/v1/auth/institution/revoke", json={"institutionUserId": other}, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 403
