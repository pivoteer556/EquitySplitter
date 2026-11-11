"""Officer session-token rotation on POST /properties/{propertyId}/owners.

Rows are seeded straight into the database so the officer's token is never rotated before the call under test. Token
iat is per second: each test advances the frozen clock so a rotation would really produce a different token, then
shows the ORIGINAL token still works after a rejection. Both success paths (new acknowledgement and an already-invited
owner) must rotate."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.models import Institution, OwnerAcknowledgement, Property, PropertyAgreement, User, UserProperty
from app.services.auth import unusable_password_hash
from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer

PROBE = "/api/v1/listings"  # any authenticated officer call; 200 proves the token is still live
BODY = {"name": "Olive Owner", "email": "olive@example.com"}
AGREEMENT = {"noticeDays": 30, "valuationMethod": "appraisal", "partialClaimMethod": "pro_rata"}


def _url(prop_id):
    return f"/api/v1/properties/{prop_id}/owners"


def _seed(session_factory, institution_id, status="pending_acknowledgement", agreement=True, invited=False):
    db = session_factory()
    try:
        prop = Property(
            institutionId=institution_id,
            address="1 Main St",
            loanAmount=1,
            currentBalance=1,
            monthlyPayment=1,
            status=status,
        )
        db.add(prop)
        db.flush()
        if agreement:
            agr = PropertyAgreement(propertyId=prop.id, **AGREEMENT)
            db.add(agr)
            db.flush()
            if invited:
                user = User(name=BODY["name"], email=BODY["email"], passwordHash=unusable_password_hash())
                db.add(user)
                db.flush()
                link = UserProperty(userId=user.id, propertyId=prop.id)
                db.add(link)
                db.flush()
                db.add(OwnerAcknowledgement(agreementId=agr.id, userPropertyId=link.id, signedAt=None))
        db.commit()
        return str(prop.id)
    finally:
        db.close()


def _own(officer):
    return UUID(officer["institution"]["id"])


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


def _assert_rejected_keeps_token(client, clock, officer, resp, status_code):
    assert resp.status_code == status_code, resp.text
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert client.get(PROBE, headers=bearer(officer["accessToken"])).status_code == 200


def _post(client, clock, officer, prop_id, body=BODY):
    _tick(clock)
    return client.post(_url(prop_id), json=body, headers=bearer(officer["accessToken"]))


def test_missing_property_keeps_token(client, officer, clock):
    resp = _post(client, clock, officer, str(uuid4()))
    _assert_rejected_keeps_token(client, clock, officer, resp, 404)


def test_other_institution_keeps_token(client, officer, clock, session_factory):
    prop_id = _seed(session_factory, _other_institution(session_factory))
    resp = _post(client, clock, officer, prop_id)
    _assert_rejected_keeps_token(client, clock, officer, resp, 403)


def test_active_property_keeps_token(client, officer, clock, session_factory):
    prop_id = _seed(session_factory, _own(officer), status="active")
    resp = _post(client, clock, officer, prop_id)
    _assert_rejected_keeps_token(client, clock, officer, resp, 403)


def test_missing_agreement_keeps_token(client, officer, clock, session_factory):
    prop_id = _seed(session_factory, _own(officer), agreement=False)
    resp = _post(client, clock, officer, prop_id)
    _assert_rejected_keeps_token(client, clock, officer, resp, 400)


@pytest.mark.parametrize("override", [{"email": "not-an-email"}, {"name": None}])
def test_invalid_body_keeps_token(client, officer, clock, session_factory, override):
    prop_id = _seed(session_factory, _own(officer))
    resp = _post(client, clock, officer, prop_id, {**BODY, **override})
    _assert_rejected_keeps_token(client, clock, officer, resp, 422)


@pytest.mark.parametrize("invited", [False, True], ids=["new_invite", "already_invited"])
def test_successful_invite_still_rotates_the_session_token(client, officer, clock, session_factory, invited):
    prop_id = _seed(session_factory, _own(officer), invited=invited)
    token = officer["accessToken"]
    resp = _post(client, clock, officer, prop_id)
    assert resp.status_code == 201, resp.text
    rotated = resp.headers["X-Refreshed-Token"]
    assert rotated != token
    _tick(clock)
    assert client.get(PROBE, headers=bearer(token)).status_code == 401  # superseded
    assert client.get(PROBE, headers=bearer(rotated)).status_code == 200


def test_wrong_identity_and_missing_token_still_rejected(client, officer, session_factory):
    prop_id = _seed(session_factory, _own(officer))
    _prop, invite = _invited(client, officer)
    assert client.post(_url(prop_id), json=BODY, headers=bearer(invite)).status_code == 403
    assert client.post(_url(prop_id), json=BODY, headers=bearer(_buyer(client).token)).status_code == 403
    assert client.post(_url(prop_id), json=BODY).status_code == 401
