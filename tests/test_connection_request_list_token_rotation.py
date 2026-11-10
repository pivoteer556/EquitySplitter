"""Session-token rotation on GET /connection-requests, for buyers (user) and officers (institution_user).

FastAPI resolves dependencies before query validation, so a rotating dependency would rotate the stored token and
THEN the 422 would be returned, which cannot carry X-Refreshed-Token. Token iat is per second: each test advances the
frozen clock so a rotation would really produce a different token, then shows the ORIGINAL token still works."""

from datetime import timedelta

import pytest

from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import URL, _buyer


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


@pytest.fixture(params=["buyer", "officer"])
def token(request, client, officer):
    if request.param == "officer":
        return officer["accessToken"]
    return _buyer(client).token


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1"])
def test_invalid_query_keeps_token(client, clock, token, query):
    _tick(clock)
    resp = client.get(f"{URL}?{query}", headers=bearer(token))
    assert resp.status_code == 422, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(URL, headers=bearer(token)).status_code == 200


def test_successful_list_still_rotates_the_session_token(client, clock, token):
    _tick(clock)
    resp = client.get(URL, headers=bearer(token))
    assert resp.status_code == 200, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(URL, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(URL, headers=bearer(rotated)).status_code == 200


def test_wrong_identity_and_missing_token_still_rejected(client, officer):
    _prop, invite = _invited(client, officer)
    assert client.get(URL, headers=bearer(invite)).status_code == 403
    assert client.get(URL).status_code == 401
