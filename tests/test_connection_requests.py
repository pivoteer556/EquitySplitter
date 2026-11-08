from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.db.session import get_db
from app.models import ConnectionRequest, InstitutionUser, Property
from tests.conftest import STRONG_PASSWORD, bearer
from tests.test_accept_invite import _invited
from tests.test_professionals import _add
from tests.test_property_flow import _property
from tests.test_property_list import _owner_token, _second_officer

API = "/api/v1"
URL = f"{API}/connection-requests"
READ_KEYS = {"id", "professionalId", "propertyId", "status", "message", "createdAt"}


class Who:
    """Carries a rotating bearer token across calls."""

    def __init__(self, client, token):
        self.client, self.token = client, token

    def call(self, method, url, **kw):
        resp = self.client.request(method, url, headers=bearer(self.token), **kw)
        self.token = resp.headers.get("X-Refreshed-Token", self.token)
        return resp

    def ask(self, professional_id, property_id, **extra):
        body = {"professionalId": str(professional_id), "propertyId": str(property_id), **extra}
        return self.call("POST", URL, json=body)

    def list(self, params=""):
        return self.call("GET", URL + params)


def _buyer(client, n=1):
    resp = client.post(
        f"{API}/auth/register",
        json={"name": f"Buyer {n}", "email": f"buyer{n}@example.com", "password": STRONG_PASSWORD},
    )
    assert resp.status_code in (200, 201), resp.text
    return Who(client, resp.json()["accessToken"])


def _pro_id(officer):
    return officer["institutionUser"]["id"]


def _setup(client, officer):
    return _property(client, officer)["id"], _pro_id(officer)


def _update(client, model, row_id, **values):
    """Direct DB write (test seam for states the API cannot produce)."""
    db = next(client.app.dependency_overrides[get_db]())
    try:
        db.query(model).filter(model.id == UUID(str(row_id))).update(values)
        db.commit()
    finally:
        db.close()


def test_buyer_creates_request(client, officer):
    prop_id, pro_id = _setup(client, officer)
    resp = _buyer(client).ask(pro_id, prop_id, message="Hello")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body) == READ_KEYS
    assert (body["professionalId"], body["propertyId"]) == (pro_id, prop_id)
    assert (body["status"], body["message"]) == ("pending", "Hello")
    assert "buyer1@example.com" not in resp.text and "institutionId" not in resp.text


def test_message_is_optional_and_limited(client, officer):
    prop_id, pro_id = _setup(client, officer)
    buyer = _buyer(client)
    assert buyer.ask(pro_id, prop_id, message="x" * 1001).status_code == 422
    assert buyer.ask(pro_id, prop_id, message="x" * 1000).status_code == 201
    other = _buyer(client, 2).ask(pro_id, prop_id)
    assert other.status_code == 201 and other.json()["message"] is None


def test_non_vocabulary_role_looks_like_missing_professional(client, officer):
    prop_id, _ = _setup(client, officer)
    legacy_id = _add(client, officer, "Ex Role", "ex@example.com", "broker").json()["id"]
    _update(client, InstitutionUser, legacy_id, role="teller")
    buyer = _buyer(client)
    real = buyer.ask(legacy_id, prop_id)
    missing = buyer.ask(uuid4(), prop_id)
    assert real.status_code == missing.status_code == 404
    assert real.json() == missing.json() == {"detail": "Professional not found"}


def test_active_or_missing_property_looks_identical(client, officer):
    prop_id, pro_id = _setup(client, officer)
    _update(client, Property, prop_id, status="active")
    buyer = _buyer(client)
    active = buyer.ask(pro_id, prop_id)
    missing = buyer.ask(pro_id, uuid4())
    assert active.status_code == missing.status_code == 404
    assert active.json() == missing.json() == {"detail": "Property not found"}


def test_duplicate_is_409_but_other_property_or_buyer_is_fine(client, officer):
    prop_id, pro_id = _setup(client, officer)
    second = _property(client, officer)["id"]
    buyer = _buyer(client)
    assert buyer.ask(pro_id, prop_id).status_code == 201
    dup = buyer.ask(pro_id, prop_id)
    assert dup.status_code == 409 and dup.json() == {"detail": "Connection already requested"}
    assert buyer.ask(pro_id, second).status_code == 201
    assert _buyer(client, 2).ask(pro_id, prop_id).status_code == 201


def test_auth_rules(client, officer):
    _prop, invite = _invited(client, officer)
    prop_id, pro_id = _setup(client, officer)
    body = {"professionalId": pro_id, "propertyId": prop_id}
    assert client.post(URL, json=body).status_code == 401
    assert Who(client, officer["accessToken"]).ask(pro_id, prop_id).status_code == 403
    assert client.post(URL, json=body, headers=bearer(invite)).status_code == 403
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=bearer(invite)).status_code == 403


def test_existing_owner_cannot_request_about_own_property(client, officer):
    prop, invite = _invited(client, officer)
    owner = Who(client, _owner_token(client, invite))
    resp = owner.ask(_pro_id(officer), prop["id"])
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Already an owner of this property"}


def test_buyer_lists_only_own(client, officer):
    prop_id, pro_a = _setup(client, officer)
    colleague = _add(client, officer, "Una Underwriter", "una@example.com", "underwriter").json()["id"]
    one, two = _buyer(client, 1), _buyer(client, 2)
    assert one.ask(pro_a, prop_id).status_code == 201
    assert one.ask(colleague, prop_id).status_code == 201
    assert two.ask(pro_a, prop_id).status_code == 201
    mine = one.list()
    assert mine.status_code == 200
    assert {r["professionalId"] for r in mine.json()} == {pro_a, colleague}
    assert all(set(r) == READ_KEYS for r in mine.json())
    assert len(two.list().json()) == 1
    assert _buyer(client, 3).list().json() == []


def test_professional_lists_only_requests_addressed_to_them(client, officer):
    prop_id, pro_id = _setup(client, officer)
    colleague_id = _add(client, officer, "Una Underwriter", "una@example.com", "underwriter").json()["id"]
    other = _second_officer(client)
    one, two = _buyer(client, 1), _buyer(client, 2)
    assert one.ask(pro_id, prop_id).status_code == 201
    assert two.ask(colleague_id, prop_id).status_code == 201
    assert two.ask(_pro_id(other), prop_id).status_code == 201
    mine = Who(client, officer["accessToken"]).list()
    assert mine.status_code == 200
    rows = mine.json()
    assert len(rows) == 1 and rows[0]["professionalId"] == pro_id
    assert set(rows[0]) == READ_KEYS | {"buyerName"} and rows[0]["buyerName"] == "Buyer 1"
    assert "@example.com" not in mine.text and "buyerId" not in mine.text
    assert [r["buyerName"] for r in Who(client, other["accessToken"]).list().json()] == ["Buyer 2"]


def test_ordering_limit_offset(client, officer):
    pros = [_pro_id(officer)]
    pros += [_add(client, officer, f"P{i}", f"p{i}@example.com", "broker").json()["id"] for i in range(2)]
    prop_id, _ = _setup(client, officer)
    buyer = _buyer(client)
    created = [buyer.ask(p, prop_id).json()["id"] for p in pros]
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i, rid in enumerate(created):
        _update(client, ConnectionRequest, rid, createdAt=base + timedelta(days=i))
    assert [r["id"] for r in buyer.list().json()] == created[::-1]
    assert [r["id"] for r in buyer.list("?limit=1&offset=1").json()] == [created[1]]
    assert buyer.list("?limit=0").status_code == 422 and buyer.list("?offset=-1").status_code == 422


def test_deleting_property_cascades_requests_via_orm(client, officer, session_factory):
    """ORM-level cascade; SQLite does not enforce the FK ON DELETE CASCADE (Postgres does)."""
    prop_id, pro_id = _setup(client, officer)
    assert _buyer(client).ask(pro_id, prop_id).status_code == 201
    db = session_factory()
    try:
        db.delete(db.get(Property, UUID(prop_id)))
        db.commit()
        assert db.query(ConnectionRequest).count() == 0
    finally:
        db.close()
