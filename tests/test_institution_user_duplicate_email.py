"""POST /institution-users with an email that already belongs to an officer is a 409 "Email already registered"
(the same status and detail as /auth/register and the bootstrap route), never an unhandled IntegrityError (500).

institutionUsers.email is UNIQUE across all institutions (one global namespace, exact match, same as the column).
Buyers live in `users`, a separate table with its own constraint, so a buyer's email does not block an officer.
A 409 cannot carry X-Refreshed-Token, so it must leave the stored session token untouched."""

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import bearer, bootstrap_officer
from tests.test_connection_requests import _buyer

PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live
USERS = "/api/v1/institution-users"
DETAIL = "Email already registered"


def _create(client, clock, officer, email, institution_id=None):
    clock["now"] += timedelta(seconds=5)
    body = {"institutionId": institution_id or officer["institution"]["id"], "name": "New Officer", "email": email}
    return client.post(USERS, json=body, headers=bearer(officer["accessToken"]))


def _assert_still_live(client, clock, officer):
    clock["now"] += timedelta(seconds=5)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


def test_duplicate_email_in_same_institution_is_409_and_keeps_token(client, clock, officer):
    client = TestClient(app, raise_server_exceptions=False)  # an unhandled error must show as a 500, not raise
    first = _create(client, clock, officer, "dup@example.com")
    assert first.status_code == 201, first.text
    token = first.headers["X-Refreshed-Token"]
    officer = {**officer, "accessToken": token}

    second = _create(client, clock, officer, "dup@example.com")
    assert second.status_code == 409, second.text
    assert second.json() == {"detail": DETAIL}
    assert "X-Refreshed-Token" not in second.headers
    _assert_still_live(client, clock, officer)


def test_officers_own_email_is_a_duplicate(client, clock, officer):
    resp = _create(client, clock, officer, "casey@example.com")
    assert resp.status_code == 409, resp.text
    assert resp.json() == {"detail": DETAIL}
    _assert_still_live(client, clock, officer)


def test_email_of_an_officer_at_another_institution_is_a_duplicate(client, clock, officer):
    bootstrap_officer(client, "Other Bank", "Other Officer", "other@example.com")
    resp = _create(client, clock, officer, "other@example.com")
    assert resp.status_code == 409, resp.text
    assert resp.json() == {"detail": DETAIL}
    _assert_still_live(client, clock, officer)


def test_buyer_email_does_not_block_an_officer(client, clock, officer):
    _buyer(client)  # registers buyer1@example.com in `users`
    resp = _create(client, clock, officer, "buyer1@example.com")
    assert resp.status_code == 201, resp.text


def test_other_institution_check_still_comes_first(client, clock, officer):
    resp = _create(client, clock, officer, "casey@example.com", institution_id=str(uuid4()))
    assert resp.status_code == 403, resp.text


def test_lost_race_is_409_rolls_back_and_keeps_the_session_usable(client, clock, officer, monkeypatch):
    """The pre-check misses (as it would when two requests interleave): the UNIQUE constraint is the backstop."""
    monkeypatch.setattr("app.api.routes.equity_splitter.ensure_officer_email_free", lambda db, email: None)
    resp = _create(client, clock, officer, "casey@example.com")
    assert resp.status_code == 409, resp.text
    assert resp.json() == {"detail": DETAIL}
    assert "X-Refreshed-Token" not in resp.headers
    ok = _create(client, clock, officer, "fresh@example.com")  # the session was rolled back, not left poisoned
    assert ok.status_code == 201, ok.text
