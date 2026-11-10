"""Officer session-token rotation on the property-listing endpoints.

A 4xx cannot carry X-Refreshed-Token (the frontend only applies it on success), so rotating the stored token before
the handler can reject would strand the caller. Token iat is per second: each test advances the frozen clock so a
rotation would really produce a different token, then shows the ORIGINAL token still works."""

from datetime import timedelta

import pytest

from tests.conftest import bearer
from tests.test_property_flow import _property
from tests.test_property_list import _second_officer
from tests.test_property_listing_transitions import MISSING, _draft, _lurl, _move, _patch
from tests.test_property_listings import BODY, _create, _url

PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _assert_rejected_keeps_token(client, clock, officer, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


def test_create_for_unknown_property_keeps_token(client, officer, clock):
    _tick(clock)
    resp = _create(client, officer, MISSING)
    _assert_rejected_keeps_token(client, clock, officer, resp, 404)


def test_create_for_other_institutions_property_keeps_token(client, officer, clock):
    other = _second_officer(client)
    prop = _property(client, other)
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _create(client, officer, prop["id"]), 404)


def test_create_with_invalid_body_keeps_token(client, officer, clock):
    prop = _property(client, officer)
    _tick(clock)
    # 422 is raised by FastAPI after dependencies resolve, so it must not follow a rotation either
    resp = _create(client, officer, prop["id"], {"askingPrice": "0"})
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


def test_list_for_unknown_property_keeps_token(client, officer, clock):
    _tick(clock)
    resp = client.get(_url(MISSING), headers=bearer(officer["accessToken"]))
    _assert_rejected_keeps_token(client, clock, officer, resp, 404)


def test_transition_unknown_listing_keeps_token(client, officer, clock):
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _move(client, officer, MISSING, "listed"), 404)


def test_transition_illegal_move_keeps_token(client, officer, clock):
    _, lst = _draft(client, officer)
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _move(client, officer, lst["id"], "draft"), 409)


def test_transition_already_listed_keeps_token(client, officer, clock):
    prop, first = _draft(client, officer)
    second = _create(client, officer, prop["id"]).json()
    assert _move(client, officer, first["id"], "listed").status_code == 200
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _move(client, officer, second["id"], "listed"), 409)


def test_transition_invalid_body_keeps_token(client, officer, clock):
    _, lst = _draft(client, officer)
    _tick(clock)
    resp = client.post(f"{_lurl(lst['id'])}/transition", json={"to": "bogus"}, headers=bearer(officer["accessToken"]))
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


def test_update_not_editable_keeps_token(client, officer, clock):
    _, lst = _draft(client, officer)
    assert _move(client, officer, lst["id"], "withdrawn").status_code == 200
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _patch(client, officer, lst["id"], {"bedrooms": 2}), 409)


def test_update_unknown_listing_keeps_token(client, officer, clock):
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _patch(client, officer, MISSING, {"bedrooms": 2}), 404)


def test_update_invalid_body_keeps_token(client, officer, clock):
    _, lst = _draft(client, officer)
    _tick(clock)
    _assert_rejected_keeps_token(client, clock, officer, _patch(client, officer, lst["id"], {"bedrooms": -1}), 422)


@pytest.mark.parametrize("op", ["create", "list", "transition", "update"])
def test_successful_call_still_rotates_the_session_token(client, officer, clock, op):
    prop, lst = _draft(client, officer)
    token = officer["accessToken"]
    h = bearer(token)
    _tick(clock)
    if op == "create":
        resp = client.post(_url(prop["id"]), json=BODY, headers=h)
    elif op == "list":
        resp = client.get(_url(prop["id"]), headers=h)
    elif op == "transition":
        resp = client.post(f"{_lurl(lst['id'])}/transition", json={"to": "listed"}, headers=h)
    else:
        resp = client.patch(_lurl(lst["id"]), json={"bedrooms": 2}, headers=h)
    assert resp.status_code in (200, 201), resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200
