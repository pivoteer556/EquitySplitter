"""Session-token rotation on GET /properties/{id} and GET /properties/{id}/owners, for buyers (user) and officers
(institution_user).

Both reads can reject the caller AFTER authentication (unknown or foreign property, a buyer not linked to it, a
malformed id), and a 4xx cannot carry X-Refreshed-Token, so rotating first would strand the caller with a dead token.
Rows are seeded straight into the database. Token iat is per second: each test advances the frozen clock so a rotation
would really produce a different token, then shows the ORIGINAL token still works after a rejection."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.models import Institution, Property, PropertyAgreement, User, UserProperty
from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

PROBE = "/api/v1/listings"  # any authenticated call; 200 proves the token is still live
BODY = {"noticeDays": 30, "valuationMethod": "appraisal", "partialClaimMethod": "pro_rata"}


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _seed(session_factory, institution_id, agreement=False, link_email=None):
    db = session_factory()
    try:
        prop = Property(
            institutionId=institution_id,
            address="1 Main St",
            loanAmount=1,
            currentBalance=1,
            monthlyPayment=1,
            status="pending_acknowledgement",
        )
        db.add(prop)
        db.flush()
        if agreement:
            db.add(PropertyAgreement(propertyId=prop.id, **BODY))
        if link_email:
            user = db.query(User).filter(User.email == link_email).one()
            db.add(UserProperty(userId=user.id, propertyId=prop.id))
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


@pytest.fixture(params=["buyer", "officer"])
def who(request, client, officer):
    if request.param == "officer":
        return SimpleNamespace(token=officer["accessToken"], officer=True, foreign_status=403)
    return SimpleNamespace(token=_buyer(client).token, officer=False, foreign_status=403)


@pytest.fixture(params=["", "/owners"])
def suffix(request):
    return request.param


@pytest.fixture(params=["unknown", "malformed", "foreign"])
def rejected(request, who, suffix, session_factory):
    """(url, expected status) for a read the caller must be turned away from."""
    if request.param == "malformed":
        prop_id, expected = "not-a-uuid", 404
    elif request.param == "unknown":
        prop_id, expected = str(uuid4()), 404
    else:  # another institution's property: the officer is not authorized (403), the buyer is not linked to it (403)
        prop_id, expected = _seed(session_factory, _other_institution(session_factory)), who.foreign_status
    return f"/api/v1/properties/{prop_id}{suffix}", expected


@pytest.fixture(params=[False, True], ids=["no-agreement", "agreement"])
def readable_url(request, who, suffix, officer, session_factory):
    link = None if who.officer else "buyer1@example.com"
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]), agreement=request.param, link_email=link)
    return f"/api/v1/properties/{prop_id}{suffix}"


def test_rejected_read_keeps_token(client, clock, who, rejected):
    url, expected = rejected
    _tick(clock)
    resp = client.get(url, headers=bearer(who.token))
    assert resp.status_code == expected, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(who.token)).status_code == 200


def test_successful_read_still_rotates_the_session_token(client, clock, who, readable_url):
    _tick(clock)
    resp = client.get(readable_url, headers=bearer(who.token))
    assert resp.status_code == 200, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != who.token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(who.token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200


@pytest.mark.parametrize("suffix", ["", "/owners"])
def test_wrong_identity_and_missing_token_still_rejected(client, officer, session_factory, suffix):
    prop_id = _seed(session_factory, UUID(officer["institution"]["id"]))
    url = f"/api/v1/properties/{prop_id}{suffix}"
    _prop, invite = _invited(client, officer)
    assert client.get(url, headers=bearer(invite)).status_code == 403
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("method, body", [("PATCH", {"address": "x"}), ("DELETE", None)])
def test_malformed_id_on_setup_writes_is_404(client, officer, method, body):
    # update_property/delete_property share _readable_property; a non-UUID id used to be a 500 (ValueError).
    resp = client.request(method, "/api/v1/properties/not-a-uuid", json=body, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Property not found"
