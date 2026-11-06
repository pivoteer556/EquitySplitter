import pytest

from tests.conftest import STRONG_PASSWORD

LOGIN_URLS = ["/api/v1/auth/login", "/api/v1/auth/institution/login"]
EMAIL = "casey@example.com"  # the bootstrapped officer; exists as an institution user
MAX_FAILURES = 5


def _login(client, url, password, email=EMAIL):
    return client.post(url, json={"email": email, "password": password})


def _fail_until_blocked(client, url, email=EMAIL):
    for _ in range(MAX_FAILURES):
        assert _login(client, url, "wrong-password", email).status_code in (401, 403)


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
