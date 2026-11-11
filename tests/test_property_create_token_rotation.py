"""Officer session-token rotation on POST /properties.

FastAPI resolves dependencies before body validation, so a rotating dependency would rotate the stored token and
THEN the 422 would be returned, which cannot carry X-Refreshed-Token. Token iat is per second: each test advances the
frozen clock so a rotation would really produce a different token, then shows the ORIGINAL token still works."""

from datetime import timedelta
from uuid import uuid4

import pytest

from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

URL = "/api/v1/properties"
PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live


def _body(officer, **overrides):
    body = {
        "institutionId": officer["institution"]["id"],
        "address": "1 Main St",
        "loanAmount": "300000",
        "currentBalance": "250000",
        "monthlyPayment": "1800",
    }
    return {**body, **overrides}


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _assert_rejected_keeps_token(client, clock, officer, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


@pytest.mark.parametrize("override", [{"address": None}, {"loanAmount": "-1"}, {"monthlyPayment": "0"}])
def test_invalid_body_keeps_token(client, officer, clock, override):
    _tick(clock)
    resp = client.post(URL, json=_body(officer, **override), headers=bearer(officer["accessToken"]))
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


def test_wrong_institution_keeps_token(client, officer, clock):
    _tick(clock)
    resp = client.post(URL, json=_body(officer, institutionId=str(uuid4())), headers=bearer(officer["accessToken"]))
    _assert_rejected_keeps_token(client, clock, officer, resp, 403)


def test_successful_create_still_rotates_the_session_token(client, officer, clock):
    token = officer["accessToken"]
    _tick(clock)
    resp = client.post(URL, json=_body(officer), headers=bearer(token))
    assert resp.status_code == 201, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200


def test_wrong_identity_and_missing_token_still_rejected(client, officer):
    _prop, invite = _invited(client, officer)
    body = _body(officer)
    assert client.post(URL, json=body, headers=bearer(invite)).status_code == 403
    assert client.post(URL, json=body, headers=bearer(_buyer(client).token)).status_code == 403
    assert client.post(URL, json=body).status_code == 401
