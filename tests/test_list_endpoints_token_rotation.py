"""Session-token rotation on GET /professionals, /properties and /listings, for buyers and officers.

A rotating dependency would rotate the stored token and THEN a 422 on limit/offset/role would be returned, which cannot
carry X-Refreshed-Token. Each test advances the frozen clock so a rotation would really produce a different token, then
shows the ORIGINAL token still works. GET /connection-requests is the 'token still live' probe."""

from datetime import timedelta

import pytest

from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import API, _buyer
from tests.test_connection_requests import URL as PROBE

ENDPOINTS = [f"{API}/professionals", f"{API}/properties", f"{API}/listings"]
PAGING = ["limit=0", "limit=201", "offset=-1"]


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


@pytest.fixture(params=["buyer", "officer"])
def token(request, client, officer):
    if request.param == "officer":
        return officer["accessToken"]
    return _buyer(client).token


@pytest.fixture(params=ENDPOINTS)
def url(request):
    return request.param


def _assert_422_keeps_token(client, clock, token, full_url):
    _tick(clock)
    resp = client.get(full_url, headers=bearer(token))
    assert resp.status_code == 422, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 200


@pytest.mark.parametrize("query", PAGING)
def test_invalid_paging_keeps_token(client, clock, token, url, query):
    _assert_422_keeps_token(client, clock, token, f"{url}?{query}")


def test_invalid_professional_role_keeps_token(client, clock, token):
    _assert_422_keeps_token(client, clock, token, f"{ENDPOINTS[0]}?role=wizard")


def test_successful_list_still_rotates_the_session_token(client, clock, token, url):
    _tick(clock)
    resp = client.get(url, headers=bearer(token))
    assert resp.status_code == 200, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200


def test_wrong_identity_and_missing_token_still_rejected(client, officer, url):
    _prop, invite = _invited(client, officer)
    assert client.get(url, headers=bearer(invite)).status_code == 403
    assert client.get(url).status_code == 401
