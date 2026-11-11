"""Officer session-token rotation on POST /institutions and POST /institution-users.

A rejection after authentication (invalid body, other institution) must not replace the stored session token: a 4xx
cannot carry X-Refreshed-Token, so the officer would be stranded. Each test advances the frozen clock so a rotation
would really produce a different token, then shows the ORIGINAL token still works. The `institution_id is None` 403 in
create_institution is unreachable via the API (InstitutionUser.institutionId is NOT NULL), so it has no test."""

from datetime import timedelta
from uuid import uuid4

import pytest

from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live
INSTITUTIONS = "/api/v1/institutions"
USERS = "/api/v1/institution-users"


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _user_body(institution_id, email="new.officer@example.com"):
    return {"institutionId": institution_id, "name": "New Officer", "email": email}


def _assert_rejected_keeps_token(client, clock, officer, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


def _post(client, clock, officer, url, body):
    _tick(clock)
    return client.post(url, json=body, headers=bearer(officer["accessToken"]))


def _assert_success_rotates(client, clock, officer, resp):
    assert resp.status_code == 201, resp.text
    token = officer["accessToken"]
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200


@pytest.mark.parametrize("body", [{}, {"name": None}])
def test_create_institution_invalid_body_keeps_token(client, officer, clock, body):
    resp = _post(client, clock, officer, INSTITUTIONS, body)
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


@pytest.mark.parametrize("override", [{"institutionId": None}, {"email": "not-an-email"}, {"role": "janitor"}])
def test_create_user_invalid_body_keeps_token(client, officer, clock, override):
    body = {**_user_body(officer["institution"]["id"]), **override}
    resp = _post(client, clock, officer, USERS, body)
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


def test_create_user_other_institution_keeps_token(client, officer, clock):
    resp = _post(client, clock, officer, USERS, _user_body(str(uuid4())))
    _assert_rejected_keeps_token(client, clock, officer, resp, 403)


def test_successful_create_institution_still_rotates_the_session_token(client, officer, clock):
    resp = _post(client, clock, officer, INSTITUTIONS, {"name": "New Bank"})
    _assert_success_rotates(client, clock, officer, resp)


def test_successful_create_user_still_rotates_the_session_token(client, officer, clock):
    resp = _post(client, clock, officer, USERS, _user_body(officer["institution"]["id"]))
    _assert_success_rotates(client, clock, officer, resp)


@pytest.mark.parametrize(("url", "body"), [(INSTITUTIONS, {"name": "New Bank"}), (USERS, None)])
def test_wrong_identity_and_missing_token_still_rejected(client, officer, url, body):
    body = body or _user_body(officer["institution"]["id"])
    _prop, invite = _invited(client, officer)
    assert client.post(url, json=body, headers=bearer(invite)).status_code == 403
    assert client.post(url, json=body, headers=bearer(_buyer(client).token)).status_code == 403
    assert client.post(url, json=body).status_code == 401
