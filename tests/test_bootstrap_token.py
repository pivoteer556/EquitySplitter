import pytest

from tests.conftest import BOOTSTRAP_HEADERS, BOOTSTRAP_TOKEN

URL = "/api/v1/auth/institution/bootstrap"
BODY = {"institutionName": "Gate Co", "officerName": "Gail", "officerEmail": "gail@example.com"}
MAX_SIGNUPS = 10


def _post(client, headers=None):
    return client.post(URL, json=BODY, headers=headers)


def test_right_token_bootstraps(client, platform_admin):
    resp = _post(client, {**platform_admin, **BOOTSTRAP_HEADERS})
    assert resp.status_code == 201
    assert resp.json()["activationToken"]


def test_missing_wrong_and_disabled_give_identical_responses(client, monkeypatch):
    missing = _post(client)
    wrong = _post(client, {"X-Bootstrap-Token": "nope"})
    monkeypatch.setattr("app.api.routes.auth.settings.bootstrap_token", "")
    disabled = _post(client, {"X-Bootstrap-Token": BOOTSTRAP_TOKEN})
    empty_header_disabled = _post(client, {"X-Bootstrap-Token": ""})
    assert missing.status_code == 404
    for other in (wrong, disabled, empty_header_disabled):
        assert (other.status_code, other.json()) == (missing.status_code, missing.json())


def test_rejected_attempts_create_nothing(client, session_factory):
    from app.models import Institution

    _post(client)
    _post(client, {"X-Bootstrap-Token": "nope"})
    with session_factory() as db:
        assert db.query(Institution).count() == 0


def test_wrong_tokens_are_rate_limited(client):
    for _ in range(MAX_SIGNUPS):
        assert _post(client, {"X-Bootstrap-Token": "nope"}).status_code == 404
    blocked = _post(client, BOOTSTRAP_HEADERS)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


@pytest.mark.parametrize("token", ["x", "é"])
def test_odd_tokens_do_not_error(client, token):
    # Non-ASCII header values must not crash the compare (hmac.compare_digest rejects non-ASCII str).
    assert _post(client, {"X-Bootstrap-Token": token.encode("latin-1")}).status_code == 404
