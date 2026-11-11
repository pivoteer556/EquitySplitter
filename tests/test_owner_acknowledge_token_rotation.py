"""Buyer/owner session-token rotation on POST /properties/{propertyId}/acknowledge.

Rows are seeded straight into the database so the owner's token is never rotated before the call under test. Token iat
is per second: each test advances the frozen clock so a rotation would really produce a different token, then shows
the ORIGINAL token still works after a rejection. Success (including the flip to active) must rotate."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.models import Institution, OwnerAcknowledgement, Property, PropertyAgreement, User, UserProperty
from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

PROBE = "/api/v1/listings"  # accepts a buyer or an officer; 200 proves the token is still live
BUYER_EMAIL = "buyer1@example.com"  # the address tests.test_connection_requests._buyer registers


def _url(prop_id):
    return f"/api/v1/properties/{prop_id}/acknowledge"


def _seed(session_factory, parts=("agreement", "link", "ack"), other_unsigned=False):
    """A pending property; `parts` picks which rows exist for the registered buyer."""
    db = session_factory()
    try:
        inst = Institution(name="Seed Bank")
        db.add(inst)
        db.flush()
        prop = Property(
            institutionId=inst.id,
            address="1 Main St",
            loanAmount=1,
            currentBalance=1,
            monthlyPayment=1,
            status="pending_acknowledgement",
        )
        db.add(prop)
        db.flush()
        agr = None
        if "agreement" in parts:
            agr = PropertyAgreement(
                propertyId=prop.id, noticeDays=30, valuationMethod="appraisal", partialClaimMethod="pro_rata"
            )
            db.add(agr)
            db.flush()
        if "link" in parts:
            buyer = db.query(User).filter(User.email == BUYER_EMAIL).one()
            link = UserProperty(userId=buyer.id, propertyId=prop.id)
            db.add(link)
            db.flush()
            if "ack" in parts and agr is not None:
                db.add(OwnerAcknowledgement(agreementId=agr.id, userPropertyId=link.id, signedAt=None))
        if other_unsigned and agr is not None:
            other = User(name="Other", email="other@example.com", passwordHash="x")
            db.add(other)
            db.flush()
            other_link = UserProperty(userId=other.id, propertyId=prop.id)
            db.add(other_link)
            db.flush()
            db.add(OwnerAcknowledgement(agreementId=agr.id, userPropertyId=other_link.id, signedAt=None))
        db.commit()
        return str(prop.id)
    finally:
        db.close()


def _status(session_factory, prop_id):
    db = session_factory()
    try:
        return db.query(Property).filter(Property.id == UUID(prop_id)).one().status
    finally:
        db.close()


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _post(client, clock, token, prop_id):
    _tick(clock)
    return client.post(_url(prop_id), headers=bearer(token))


def _assert_rejected_keeps_token(client, clock, token, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 200


def test_missing_property_keeps_token(client, clock):
    token = _buyer(client).token
    resp = _post(client, clock, token, uuid4())
    _assert_rejected_keeps_token(client, clock, token, resp, 404)


def test_missing_agreement_keeps_token(client, clock, session_factory):
    token = _buyer(client).token
    resp = _post(client, clock, token, _seed(session_factory, parts=()))
    _assert_rejected_keeps_token(client, clock, token, resp, 404)


def test_not_an_owner_keeps_token(client, clock, session_factory):
    token = _buyer(client).token
    resp = _post(client, clock, token, _seed(session_factory, parts=("agreement",)))
    _assert_rejected_keeps_token(client, clock, token, resp, 403)


def test_missing_acknowledgement_keeps_token(client, clock, session_factory):
    token = _buyer(client).token
    resp = _post(client, clock, token, _seed(session_factory, parts=("agreement", "link")))
    _assert_rejected_keeps_token(client, clock, token, resp, 404)


@pytest.mark.parametrize("other_unsigned", [False, True], ids=["last_owner_goes_active", "stays_pending"])
def test_successful_acknowledge_still_rotates_the_session_token(client, clock, session_factory, other_unsigned):
    token = _buyer(client).token
    prop_id = _seed(session_factory, other_unsigned=other_unsigned)
    resp = _post(client, clock, token, prop_id)
    assert resp.status_code == 200, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    assert _status(session_factory, prop_id) == ("pending_acknowledgement" if other_unsigned else "active")
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200


def test_wrong_identity_and_missing_token_still_rejected(client, officer, session_factory):
    _buyer(client)
    prop_id = _seed(session_factory)
    assert client.post(_url(prop_id), headers=bearer(officer["accessToken"])).status_code == 403
    _prop, invite = _invited(client, officer)
    assert client.post(_url(prop_id), headers=bearer(invite)).status_code == 403
    assert client.post(_url(prop_id)).status_code == 401
