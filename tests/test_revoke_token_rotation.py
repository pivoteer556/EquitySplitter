"""Officer session-token rotation on POST /auth/institution/revoke.

Revoke is self-only and a successful revoke kills the caller's token, so it never rotates. A rejection after
authentication (another officer's id, a malformed id) must leave the stored session token alone: the same bearer
token still works on the next call."""

from datetime import timedelta
from uuid import uuid4

import pytest

from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

URL = "/api/v1/auth/institution/revoke"
PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _revoke(client, clock, token, body):
    _tick(clock)
    return client.post(URL, json=body, headers=bearer(token))


@pytest.mark.parametrize(
    ("body", "status_code"),
    [({"institutionUserId": str(uuid4())}, 403), ({"institutionUserId": "not-a-uuid"}, 422)],
)
def test_rejected_revoke_keeps_token(client, officer, clock, body, status_code):
    resp = _revoke(client, clock, officer["accessToken"], body)
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


@pytest.mark.parametrize("body", [{}, None])
def test_self_revoke_is_204_without_rotation_and_kills_the_token(client, officer, clock, body):
    token = officer["accessToken"]
    if body is None:
        body = {"institutionUserId": officer["institutionUser"]["id"]}
    resp = _revoke(client, clock, token, body)
    assert resp.status_code == 204, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    after = client.get(PROBE, headers=bearer(token))
    assert after.status_code == 401
    assert after.json()["detail"] == "Institution token revoked"


def test_wrong_identity_and_missing_token_still_rejected(client, officer):
    _prop, invite = _invited(client, officer)
    assert client.post(URL, json={}, headers=bearer(invite)).status_code == 403
    assert client.post(URL, json={}, headers=bearer(_buyer(client).token)).status_code == 403
    assert client.post(URL, json={}).status_code == 401
