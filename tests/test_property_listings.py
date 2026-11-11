import pytest
from sqlalchemy.exc import IntegrityError

from app.models import PropertyListing
from tests.conftest import bearer
from tests.test_listings import _buyer_token
from tests.test_property_flow import _property
from tests.test_property_list import _second_officer

API = "/api/v1"
BODY = {"askingPrice": "350000.00", "bedrooms": 3, "bathrooms": "2.5", "squareFeet": 1800, "description": "Corner lot"}


def _url(property_id):
    return f"{API}/properties/{property_id}/listings"


def _create(client, officer, property_id, body=None):
    return client.post(_url(property_id), json=BODY if body is None else body, headers=bearer(officer["accessToken"]))


def test_create_returns_draft_listing(client, officer):
    prop = _property(client, officer)
    resp = _create(client, officer, prop["id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["propertyId"] == prop["id"]
    assert body["askingPrice"] in ("350000.00", 350000.0, "350000")
    assert (body["bedrooms"], body["squareFeet"], body["description"]) == (3, 1800, "Corner lot")
    assert float(body["bathrooms"]) == 2.5
    assert body["listedAt"] is None and body["delistedAt"] is None and body["id"] and body["createdAt"]


def test_create_with_only_price(client, officer):
    prop = _property(client, officer)
    resp = _create(client, officer, prop["id"], {"askingPrice": "1"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["bedrooms"] is None


@pytest.mark.parametrize(
    "patch",
    [
        {"askingPrice": "0"},
        {"askingPrice": "-5"},
        {"askingPrice": None},
        {"bedrooms": -1},
        {"bathrooms": "-0.5"},
        {"squareFeet": 0},
        {"status": "listed"},
        {"id": "x"},
    ],
)
def test_create_validation(client, officer, patch):
    prop = _property(client, officer)
    assert _create(client, officer, prop["id"], {**BODY, **patch}).status_code == 422


def test_missing_price_is_422(client, officer):
    prop = _property(client, officer)
    assert _create(client, officer, prop["id"], {"bedrooms": 2}).status_code == 422


def test_other_institution_gets_403_unknown_is_404(client, officer):
    prop = _property(client, officer)
    other = _second_officer(client)
    cross = _create(client, other, prop["id"])
    unknown = _create(client, other, "00000000-0000-4000-8000-000000000000")
    assert cross.status_code == 403
    assert cross.json() == {"detail": "Loan officer not authorized for institution"}
    assert unknown.status_code == 404
    listing = client.get(_url(prop["id"]), headers=bearer(other["accessToken"]))
    assert listing.status_code == 403


def test_unknown_property_404_for_owner_institution(client, officer):
    assert _create(client, officer, "00000000-0000-4000-8000-000000000000").status_code == 404
    resp = client.get(_url("00000000-0000-4000-8000-000000000000"), headers=bearer(officer["accessToken"]))
    assert resp.status_code == 404


def test_auth_required(client, officer):
    prop = _property(client, officer)
    assert client.post(_url(prop["id"]), json=BODY).status_code == 401
    assert client.get(_url(prop["id"])).status_code == 401
    assert client.get(_url(prop["id"]), headers=bearer("not-a-jwt")).status_code == 401
    buyer = _buyer_token(client)
    assert client.post(_url(prop["id"]), json=BODY, headers=bearer(buyer)).status_code == 403
    assert client.get(_url(prop["id"]), headers=bearer(buyer)).status_code == 403


def test_list_newest_first_scoped_to_property(client, officer, session_factory):
    p1 = _property(client, officer)
    p2 = _property(client, officer)
    ids = [_create(client, officer, p1["id"], {"askingPrice": str(100 + i)}).json()["id"] for i in range(3)]
    other_id = _create(client, officer, p2["id"]).json()["id"]
    resp = client.get(_url(p1["id"]), headers=bearer(officer["accessToken"]))
    assert resp.status_code == 200
    got = [row["id"] for row in resp.json()]
    assert sorted(got) == sorted(ids) and other_id not in got
    created = [row["createdAt"] for row in resp.json()]
    assert created == sorted(created, reverse=True)


def test_list_empty(client, officer):
    prop = _property(client, officer)
    resp = client.get(_url(prop["id"]), headers=bearer(officer["accessToken"]))
    assert resp.status_code == 200 and resp.json() == []


def _row(property_id, status):
    return PropertyListing(propertyId=property_id, status=status, askingPrice=1)


def test_db_allows_many_non_listed_rows_per_property(client, officer, session_factory):
    import uuid

    pid = uuid.UUID(_property(client, officer)["id"])
    with session_factory() as db:
        db.add_all([_row(pid, "draft"), _row(pid, "draft"), _row(pid, "withdrawn"), _row(pid, "withdrawn")])
        db.add(_row(pid, "listed"))
        db.commit()


def test_db_rejects_two_listed_rows_per_property(client, officer, session_factory):
    import uuid

    pid = uuid.UUID(_property(client, officer)["id"])
    with session_factory() as db:
        db.add_all([_row(pid, "listed"), _row(pid, "listed")])
        with pytest.raises(IntegrityError):
            db.commit()


def test_status_vocabulary_in_one_place():
    from app.models.property_listing import LISTING_STATUSES

    assert LISTING_STATUSES == ("draft", "listed", "withdrawn", "sold")
