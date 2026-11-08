from app.models import OwnerAcknowledgement, PropertyAgreement
from tests.test_accept_invite import _invited
from tests.test_property_flow import _agreement, _property
from tests.test_property_list import _owner_token
from tests.test_property_officer_read import _get, _urls


def test_officer_reads_detail_of_property_without_agreement(client, officer):
    prop = _property(client, officer)
    resp, _ = _get(client, officer["accessToken"], _urls(prop["id"])[0])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agreement"] is None
    assert body["property"]["id"] == prop["id"]
    assert body["property"]["status"] == "pending_acknowledgement"


def test_officer_reads_owners_of_property_without_agreement(client, officer):
    prop = _property(client, officer)
    resp, _ = _get(client, officer["accessToken"], _urls(prop["id"])[1])
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"owners": []}


def test_linked_owner_reads_detail_when_agreement_is_absent(client, officer, session_factory):
    # The API cannot produce this state (invites require an agreement), so the agreement is removed directly in the DB.
    prop, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    with session_factory() as db:
        db.query(OwnerAcknowledgement).delete()
        db.query(PropertyAgreement).delete()
        db.commit()
    resp, token = _get(client, token, _urls(prop["id"])[0])
    assert resp.status_code == 200, resp.text
    assert resp.json()["agreement"] is None
    assert resp.json()["property"]["status"] == "pending_acknowledgement"
    resp, _ = _get(client, token, _urls(prop["id"])[1])
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"owners": []}


def test_property_with_agreement_keeps_its_shape(client, officer):
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    resp, _ = _get(client, officer["accessToken"], _urls(prop["id"])[0])
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["agreement"]) >= {"id", "propertyId", "noticeDays", "valuationMethod", "effectiveAt"}
