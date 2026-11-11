"""Officer session-token rotation on PATCH and DELETE /properties/{propertyId}.

Rows are seeded straight into the database so the officer's token is never rotated before the call under test. Token
iat is per second: each test advances the frozen clock so a rotation would really produce a different token, then
shows the ORIGINAL token still works after a rejection."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.models import Institution, Property
from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live
CHANGE = {"loanAmount": 5}


def _url(prop_id):
    return f"/api/v1/properties/{prop_id}"


def _seed(session_factory, institution_id=None, status="pending_acknowledgement", officer=None):
    db = session_factory()
    try:
        if institution_id is None:
            institution_id = UUID(officer["institution"]["id"])
        prop = Property(
            institutionId=institution_id,
            address="1 Main St",
            loanAmount=1,
            currentBalance=1,
            monthlyPayment=1,
            status=status,
        )
        db.add(prop)
        db.commit()
        return str(prop.id)
    finally:
        db.close()


def _other_institution(session_factory):
    db = session_factory()
    try:
        inst = Institution(name="Other Bank")
        db.add(inst)
        db.commit()
        return inst.id
    finally:
        db.close()


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _call(client, clock, officer, verb, target):
    prop_id, body = target if isinstance(target, tuple) else (target, CHANGE)
    _tick(clock)
    headers = bearer(officer["accessToken"])
    if verb == "patch":
        return client.patch(_url(prop_id), json=body, headers=headers)
    return client.delete(_url(prop_id), headers=headers)


def _assert_rejected_keeps_token(client, clock, officer, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


VERBS = pytest.mark.parametrize("verb", ["patch", "delete"])


@VERBS
def test_missing_property_keeps_token(client, officer, clock, verb):
    resp = _call(client, clock, officer, verb, str(uuid4()))
    _assert_rejected_keeps_token(client, clock, officer, resp, 404)


@VERBS
def test_other_institution_keeps_token(client, officer, clock, session_factory, verb):
    prop_id = _seed(session_factory, institution_id=_other_institution(session_factory))
    resp = _call(client, clock, officer, verb, prop_id)
    _assert_rejected_keeps_token(client, clock, officer, resp, 403)


@VERBS
def test_active_property_keeps_token(client, officer, clock, session_factory, verb):
    prop_id = _seed(session_factory, officer=officer, status="active")
    resp = _call(client, clock, officer, verb, prop_id)
    _assert_rejected_keeps_token(client, clock, officer, resp, 403)


@pytest.mark.parametrize("body", [{"loanAmount": -1}, {"address": None}, {}])
def test_invalid_patch_body_keeps_token(client, officer, clock, session_factory, body):
    prop_id = _seed(session_factory, officer=officer)
    resp = _call(client, clock, officer, "patch", (prop_id, body))
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


def _assert_rotated(client, clock, officer, resp, status_code):
    assert resp.status_code == status_code, resp.text
    token = officer["accessToken"]
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    probe = client.get(PROBE, headers=bearer(rotated))
    assert probe.status_code == 200
    return probe.headers["X-Refreshed-Token"]  # the probe rotated again: the newest live token


def test_successful_patch_still_rotates_the_session_token(client, officer, clock, session_factory):
    prop_id = _seed(session_factory, officer=officer)
    resp = _call(client, clock, officer, "patch", prop_id)
    assert resp.json()["loanAmount"] == "5.00"
    _assert_rotated(client, clock, officer, resp, 200)


def test_successful_delete_still_rotates_the_session_token(client, officer, clock, session_factory):
    prop_id = _seed(session_factory, officer=officer)
    resp = _call(client, clock, officer, "delete", prop_id)
    newest = _assert_rotated(client, clock, officer, resp, 204)
    _tick(clock)
    assert client.get(_url(prop_id), headers=bearer(newest)).status_code == 404  # really deleted


@VERBS
def test_wrong_identity_and_missing_token_still_rejected(client, officer, session_factory, verb):
    prop_id = _seed(session_factory, officer=officer)
    _prop, invite = _invited(client, officer)
    send = client.patch if verb == "patch" else client.delete
    kwargs = {"json": CHANGE} if verb == "patch" else {}
    assert send(_url(prop_id), headers=bearer(invite), **kwargs).status_code == 403
    assert send(_url(prop_id), headers=bearer(_buyer(client).token), **kwargs).status_code == 403
    assert send(_url(prop_id), **kwargs).status_code == 401
