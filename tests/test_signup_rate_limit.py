from tests.conftest import STRONG_PASSWORD

MAX_SIGNUPS = 10


def _register(client, i, headers=None):
    return client.post(
        "/api/v1/auth/register",
        json={"name": f"U{i}", "email": f"u{i}@example.com", "password": STRONG_PASSWORD},
        headers=headers,
    )


def _bootstrap(client, i, headers=None):
    return client.post(
        "/api/v1/auth/institution/bootstrap",
        json={"institutionName": f"Inst {i}", "officerName": f"O{i}", "officerEmail": f"o{i}@example.com", "officerPassword": STRONG_PASSWORD},
        headers=headers,
    )


def test_register_is_limited_per_ip(client):
    for i in range(MAX_SIGNUPS):
        assert _register(client, i).status_code == 201
    blocked = _register(client, 99)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_bootstrap_is_limited_per_ip(client):
    for i in range(MAX_SIGNUPS):
        assert _bootstrap(client, i).status_code == 201
    assert _bootstrap(client, 99).status_code == 429


def test_register_and_bootstrap_share_one_budget(client):
    for i in range(MAX_SIGNUPS):
        assert _register(client, i).status_code == 201
    assert _bootstrap(client, 99).status_code == 429


def test_rejected_attempts_count_too(client):
    # Duplicate-email probing (409) must not be free.
    assert _register(client, 0).status_code == 201
    for _ in range(MAX_SIGNUPS - 1):
        assert _register(client, 0).status_code == 409
    assert _register(client, 0).status_code == 429


def test_signup_budget_is_per_client_ip_behind_trusted_proxy(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.settings.trusted_proxy_hops", 1)
    for i in range(MAX_SIGNUPS):
        assert _register(client, i, {"X-Forwarded-For": "203.0.113.7"}).status_code == 201
    assert _register(client, 50, {"X-Forwarded-For": "203.0.113.7"}).status_code == 429
    assert _register(client, 51, {"X-Forwarded-For": "203.0.113.8"}).status_code == 201


def test_signup_limit_does_not_affect_login_counters(client, officer):
    for i in range(MAX_SIGNUPS):
        _register(client, i)
    resp = client.post("/api/v1/auth/institution/login", json={"email": "casey@example.com", "password": STRONG_PASSWORD})
    assert resp.status_code == 200
