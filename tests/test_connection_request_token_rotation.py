"""Buyer session-token rotation on POST /connection-requests.

A 4xx cannot carry X-Refreshed-Token (the frontend only applies it on success), so rotating the stored token before
the handler can reject would strand the buyer. Token iat is per second: each test advances the frozen clock so a
rotation would really produce a different token, then shows the ORIGINAL token still works."""

from datetime import timedelta
from uuid import uuid4

from app.models import Property
from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import URL, Who, _buyer, _pro_id, _setup, _update
from tests.test_property_list import _owner_token


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _post(client, token, body):
    return client.post(URL, json=body, headers=bearer(token))


def _body(pro_id, prop_id):
    return {"professionalId": str(pro_id), "propertyId": str(prop_id)}


def _assert_rejected_keeps_token(client, clock, token, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(URL, headers=bearer(token)).status_code == 200


def test_unknown_professional_keeps_token(client, officer, clock):
    prop_id, _ = _setup(client, officer)
    token = _buyer(client).token
    _tick(clock)
    resp = _post(client, token, _body(uuid4(), prop_id))
    _assert_rejected_keeps_token(client, clock, token, resp, 404)


def test_unknown_property_keeps_token(client, officer, clock):
    _, pro_id = _setup(client, officer)
    token = _buyer(client).token
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, token, _post(client, token, _body(pro_id, uuid4())), 404)


def test_not_pending_property_keeps_token(client, officer, clock):
    prop_id, pro_id = _setup(client, officer)
    _update(client, Property, prop_id, status="active")
    token = _buyer(client).token
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, token, _post(client, token, _body(pro_id, prop_id)), 404)


def test_existing_owner_keeps_token(client, officer, clock):
    prop, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    _tick(clock)
    resp = _post(client, token, _body(_pro_id(officer), prop["id"]))
    _assert_rejected_keeps_token(client, clock, token, resp, 409)


def test_duplicate_request_keeps_token(client, officer, clock):
    prop_id, pro_id = _setup(client, officer)
    buyer = _buyer(client)
    first = buyer.ask(pro_id, prop_id)
    assert first.status_code == 201
    token = buyer.token
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, token, _post(client, token, _body(pro_id, prop_id)), 409)


def test_lost_race_integrity_error_keeps_token(client, officer, clock, monkeypatch):
    prop_id, pro_id = _setup(client, officer)
    buyer = _buyer(client)
    assert buyer.ask(pro_id, prop_id).status_code == 201
    token = buyer.token
    # Skip the pre-check so the UNIQUE constraint (the backstop for a lost race) is what rejects the insert
    monkeypatch.setattr("app.api.routes.connection_requests._check_targets", lambda *a, **k: None)
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, token, _post(client, token, _body(pro_id, prop_id)), 409)


def test_invalid_body_keeps_token(client, officer, clock):
    prop_id, pro_id = _setup(client, officer)
    token = _buyer(client).token
    _tick(clock)
    # 422 is raised by FastAPI after dependencies resolve, so it must not follow a rotation either
    resp = _post(client, token, {**_body(pro_id, prop_id), "message": "x" * 1001})
    _assert_rejected_keeps_token(client, clock, token, resp, 422)


def test_successful_request_still_rotates_the_session_token(client, officer, clock):
    prop_id, pro_id = _setup(client, officer)
    token = _buyer(client).token
    _tick(clock)
    resp = _post(client, token, _body(pro_id, prop_id))
    assert resp.status_code == 201, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(URL, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(URL, headers=bearer(rotated)).status_code == 200


def test_wrong_identity_and_missing_token_still_rejected(client, officer):
    prop_id, pro_id = _setup(client, officer)
    assert Who(client, officer["accessToken"]).ask(pro_id, prop_id).status_code == 403
    assert client.post(URL, json=_body(pro_id, prop_id)).status_code == 401
