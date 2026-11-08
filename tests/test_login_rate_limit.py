import pytest

from tests.conftest import STRONG_PASSWORD

LOGIN_URLS = ["/api/v1/auth/login", "/api/v1/auth/institution/login"]
EMAIL = "casey@example.com"  # the bootstrapped officer; exists as an institution user
MAX_FAILURES = 5


def _login(client, url, password, email=EMAIL):
    return client.post(url, json={"email": email, "password": password})


def _fail_until_blocked(client, url, email=EMAIL):
    for _ in range(MAX_FAILURES):
        assert _login(client, url, "wrong-password", email).status_code == 401


@pytest.mark.parametrize("url", LOGIN_URLS)
def test_repeated_failures_return_429_with_retry_after(client, officer, url):
    _fail_until_blocked(client, url)
    resp = _login(client, url, "wrong-password")
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1


def test_correct_password_is_also_blocked(client, officer):
    url = "/api/v1/auth/institution/login"
    _fail_until_blocked(client, url)
    assert _login(client, url, STRONG_PASSWORD).status_code == 429


def test_success_resets_counter(client, officer):
    url = "/api/v1/auth/institution/login"
    for _ in range(MAX_FAILURES - 1):
        assert _login(client, url, "wrong-password").status_code == 401
    assert _login(client, url, STRONG_PASSWORD).status_code == 200
    for _ in range(MAX_FAILURES - 1):
        assert _login(client, url, "wrong-password").status_code == 401


def test_counters_are_independent_per_email_and_endpoint(client, officer):
    _fail_until_blocked(client, "/api/v1/auth/institution/login")
    assert _login(client, "/api/v1/auth/institution/login", "x", "other@example.com").status_code != 429
    assert _login(client, "/api/v1/auth/login", "x").status_code != 429


URL = "/api/v1/auth/institution/login"


def _login_from(client, forwarded_for, password="wrong-password"):
    return client.post(URL, json={"email": EMAIL, "password": password}, headers={"X-Forwarded-For": forwarded_for})


def test_forwarded_for_ignored_when_no_trusted_proxy(client, officer, monkeypatch):
    # Default (0 trusted hops): a client must not evade the limit by rotating a spoofed header.
    monkeypatch.setattr("app.api.routes.auth.settings.trusted_proxy_hops", 0)
    for i in range(MAX_FAILURES):
        assert _login_from(client, f"10.0.0.{i}").status_code == 401
    assert _login_from(client, "10.0.0.99").status_code == 429


def test_clients_behind_one_trusted_proxy_have_separate_counters(client, officer, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.settings.trusted_proxy_hops", 1)
    for _ in range(MAX_FAILURES):
        assert _login_from(client, "203.0.113.7").status_code == 401
    assert _login_from(client, "203.0.113.7").status_code == 429
    # A different real client (same proxy, same victim email) is not locked out.
    assert _login_from(client, "203.0.113.8", STRONG_PASSWORD).status_code == 200


def test_spoofed_left_entries_do_not_evade_trusted_proxy_limit(client, officer, monkeypatch):
    # The trusted proxy appends the real peer on the right; anything the client prepends is untrusted.
    monkeypatch.setattr("app.api.routes.auth.settings.trusted_proxy_hops", 1)
    for i in range(MAX_FAILURES):
        assert _login_from(client, f"spoof-{i}, 203.0.113.7").status_code == 401
    assert _login_from(client, "spoof-new, 203.0.113.7").status_code == 429
