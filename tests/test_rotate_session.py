"""The shared rotate_session helper (app/api/deps/auth.py): sets X-Refreshed-Token and supersedes the old token, for a
buyer (user) and an officer (institution_user). Called directly with a Response and a session; the probes go through
the TestClient. Token iat is per second, so the frozen clock advances before each rotation."""

from datetime import timedelta
from uuid import UUID

import pytest
from fastapi import Response

from app.api.deps.auth import Principal, rotate_session
from app.services.auth import decode_token
from tests.conftest import bearer
from tests.test_connection_requests import URL, _buyer


@pytest.fixture(params=["buyer", "officer"])
def token(request, client, officer):
    if request.param == "officer":
        return officer["accessToken"]
    return _buyer(client).token


def test_rotate_session_issues_new_token_and_supersedes_old(client, session_factory, clock, token):
    clock["now"] += timedelta(seconds=5)
    with session_factory() as db:
        claims = decode_token(db, token)
        principal = Principal(user_id=UUID(claims["sub"]), user_type=claims["userType"])
        response = Response()
        rotate_session(db, principal, response)
    rotated = response.headers["X-Refreshed-Token"]
    assert rotated != token
    clock["now"] += timedelta(seconds=5)
    assert client.get(URL, headers=bearer(token)).status_code == 401
    assert client.get(URL, headers=bearer(rotated)).status_code == 200
