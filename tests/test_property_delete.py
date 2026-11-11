from uuid import UUID, uuid4

from app.models import Loan, OwnerAcknowledgement, PropertyAgreement, User, UserProperty
from tests.conftest import bearer
from tests.test_accept_invite import _invite, _invited
from tests.test_property_flow import _agreement, _property
from tests.test_property_list import _owner_token, _second_officer

API = "/api/v1"
ACTIVE_MSG = "Property is active; setup writes are closed"


class Session:
    """Carries the rotating bearer token across calls."""

    def __init__(self, client, token):
        self.client, self.token = client, token

    def call(self, method, path):
        resp = self.client.request(method, f"{API}{path}", headers=bearer(self.token))
        self.token = resp.headers.get("X-Refreshed-Token", self.token)
        return resp

    def delete(self, prop_id):
        return self.call("DELETE", f"/properties/{prop_id}")

    def ids(self, path):
        resp = self.call("GET", path)
        assert resp.status_code == 200, resp.text
        return [p["id"] for p in resp.json()]


def _counts(session_factory, prop_id):
    """Row counts of the property's children. SQLite tests skip FK cascade, so this proves ORM cascades."""
    pid = UUID(prop_id)
    db = session_factory()
    try:
        links = db.query(UserProperty).filter(UserProperty.propertyId == pid).all()
        agreements = db.query(PropertyAgreement).filter(PropertyAgreement.propertyId == pid).count()
        acks = db.query(OwnerAcknowledgement).filter(OwnerAcknowledgement.userPropertyId.in_([u.id for u in links]))
        return {
            "loans": db.query(Loan).filter(Loan.propertyId == pid).count(),
            "agreements": agreements,
            "links": len(links),
            "acks": acks.count(),
        }
    finally:
        db.close()


def _user_count(session_factory):
    db = session_factory()
    try:
        return db.query(User).count()
    finally:
        db.close()


def test_officer_deletes_own_pending_property(client, officer, session_factory):
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    s = Session(client, officer["accessToken"])
    assert prop["id"] in s.ids("/properties")
    assert prop["id"] in s.ids("/listings")
    assert _counts(session_factory, prop["id"])["loans"] == 1

    resp = s.delete(prop["id"])
    assert resp.status_code == 204, resp.text
    assert resp.content == b""
    assert s.call("GET", f"/properties/{prop['id']}").status_code == 404
    assert prop["id"] not in s.ids("/properties")
    assert prop["id"] not in s.ids("/listings")
    assert _counts(session_factory, prop["id"]) == {"loans": 0, "agreements": 0, "links": 0, "acks": 0}


def test_delete_with_owners_and_partial_acknowledgement(client, officer, session_factory):
    prop, invite = _invited(client, officer)
    assert _invite(client, officer, prop["id"], "second@example.com").status_code == 201
    owner = _owner_token(client, invite)
    assert client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(owner)).status_code == 200
    s = Session(client, officer["accessToken"])
    assert s.call("GET", f"/properties/{prop['id']}").json()["property"]["status"] != "active"
    before = _counts(session_factory, prop["id"])  # one ack row per invite, one acknowledged
    assert before == {"loans": 1, "agreements": 1, "links": 2, "acks": 2}
    users = _user_count(session_factory)

    assert s.delete(prop["id"]).status_code == 204
    assert _counts(session_factory, prop["id"]) == {"loans": 0, "agreements": 0, "links": 0, "acks": 0}
    assert _user_count(session_factory) == users  # invited accounts remain


def test_active_property_cannot_be_deleted(client, officer, session_factory):
    prop, invite = _invited(client, officer)
    owner = _owner_token(client, invite)
    assert client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(owner)).status_code == 200
    s = Session(client, officer["accessToken"])
    assert s.call("GET", f"/properties/{prop['id']}").json()["property"]["status"] == "active"
    before = _counts(session_factory, prop["id"])  # one ack row per invite, one acknowledged

    resp = s.delete(prop["id"])
    assert resp.status_code == 403
    assert resp.json()["detail"] == ACTIVE_MSG
    assert _counts(session_factory, prop["id"]) == before
    assert s.call("GET", f"/properties/{prop['id']}").status_code == 200


def test_other_institution_is_forbidden_missing_is_404(client, officer):
    other = _second_officer(client)
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    s = Session(client, other["accessToken"])
    real = s.delete(prop["id"])
    missing = s.delete(str(uuid4()))
    assert (real.status_code, real.json()) == (403, {"detail": "Loan officer not authorized for institution"})
    assert (missing.status_code, missing.json()) == (404, {"detail": "Property not found"})
    assert Session(client, officer["accessToken"]).call("GET", f"/properties/{prop['id']}").status_code == 200


def test_owner_unauthenticated_and_invite_tokens(client, officer):
    prop, invite = _invited(client, officer)
    url = f"{API}/properties/{prop['id']}"
    assert client.delete(url, headers=bearer(invite)).status_code == 403
    assert client.delete(url).status_code == 401
    assert client.delete(url, headers=bearer("not-a-jwt")).status_code == 401
    owner = _owner_token(client, invite)
    assert client.delete(url, headers=bearer(owner)).status_code == 403
    assert Session(client, officer["accessToken"]).call("GET", f"/properties/{prop['id']}").status_code == 200


def test_second_delete_is_404(client, officer):
    prop = _property(client, officer)
    s = Session(client, officer["accessToken"])
    assert s.delete(prop["id"]).status_code == 204
    again = s.delete(prop["id"])
    assert again.status_code == 404
    assert again.json() == {"detail": "Property not found"}
