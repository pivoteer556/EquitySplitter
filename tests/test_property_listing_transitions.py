import pytest

from tests.conftest import bearer
from tests.test_listings import _buyer_token
from tests.test_property_flow import _property
from tests.test_property_list import _second_officer
from tests.test_property_listings import BODY, _create

API = "/api/v1"
MISSING = "00000000-0000-4000-8000-000000000000"


def _lurl(listing_id):
    return f"{API}/property-listings/{listing_id}"


def _move(client, officer, listing_id, to):
    return client.post(f"{_lurl(listing_id)}/transition", json={"to": to}, headers=bearer(officer["accessToken"]))


def _patch(client, officer, listing_id, body):
    return client.patch(_lurl(listing_id), json=body, headers=bearer(officer["accessToken"]))


def _draft(client, officer, prop=None):
    prop = prop or _property(client, officer)
    return prop, _create(client, officer, prop["id"]).json()


def test_draft_to_listed_sets_listed_at(client, officer):
    _, lst = _draft(client, officer)
    resp = _move(client, officer, lst["id"], "listed")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "listed" and body["listedAt"] and body["delistedAt"] is None and body["id"] == lst["id"]


def test_listed_to_withdrawn_sets_delisted_at(client, officer):
    _, lst = _draft(client, officer)
    _move(client, officer, lst["id"], "listed")
    body = _move(client, officer, lst["id"], "withdrawn").json()
    assert body["status"] == "withdrawn" and body["delistedAt"] and body["listedAt"]


def test_draft_to_withdrawn_leaves_dates_null(client, officer):
    _, lst = _draft(client, officer)
    body = _move(client, officer, lst["id"], "withdrawn").json()
    assert body["status"] == "withdrawn" and body["listedAt"] is None and body["delistedAt"] is None


@pytest.mark.parametrize("to", ["sold"])
def test_sold_is_not_available_yet(client, officer, to):
    # BACKLOG 2h: sold needs the loan pipeline, which is not built.
    _, lst = _draft(client, officer)
    for start in (None, "listed"):
        if start:
            _move(client, officer, lst["id"], start)
        resp = _move(client, officer, lst["id"], to)
        assert resp.status_code == 409 and resp.json()["detail"] == "Not available yet"
    assert _move(client, officer, lst["id"], "withdrawn").json()["status"] == "withdrawn"
    assert _move(client, officer, lst["id"], to).status_code == 409


def test_illegal_moves_are_409(client, officer):
    _, lst = _draft(client, officer)
    assert _move(client, officer, lst["id"], "draft").status_code == 409  # same status
    _move(client, officer, lst["id"], "listed")
    assert _move(client, officer, lst["id"], "listed").status_code == 409
    assert _move(client, officer, lst["id"], "draft").status_code == 409
    _move(client, officer, lst["id"], "withdrawn")
    assert _move(client, officer, lst["id"], "listed").status_code == 409
    assert _move(client, officer, lst["id"], "draft").status_code == 409
    assert _move(client, officer, lst["id"], "withdrawn").status_code == 409


@pytest.mark.parametrize("body", [{"to": "bogus"}, {}, {"to": None}, {"to": "listed", "x": 1}])
def test_transition_validation_422(client, officer, body):
    _, lst = _draft(client, officer)
    resp = client.post(f"{_lurl(lst['id'])}/transition", json=body, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 422


def test_second_listed_on_property_is_409_and_first_stays(client, officer):
    prop, first = _draft(client, officer)
    second = _create(client, officer, prop["id"]).json()
    assert _move(client, officer, first["id"], "listed").status_code == 200
    resp = _move(client, officer, second["id"], "listed")
    assert resp.status_code == 409 and "already" in resp.json()["detail"]
    got = client.get(f"{API}/properties/{prop['id']}/listings", headers=bearer(officer["accessToken"])).json()
    rows = {r["id"]: r for r in got}
    assert rows[first["id"]]["status"] == "listed" and rows[second["id"]]["status"] == "draft"
    assert rows[second["id"]]["listedAt"] is None


def test_withdraw_then_list_other_draft(client, officer):
    prop, first = _draft(client, officer)
    second = _create(client, officer, prop["id"]).json()
    _move(client, officer, first["id"], "listed")
    _move(client, officer, first["id"], "withdrawn")
    assert _move(client, officer, second["id"], "listed").status_code == 200


def test_integrity_error_is_409(client, officer, monkeypatch):
    # The pre-check can race; the unique index is the backstop.
    from app.api.routes import property_listings

    monkeypatch.setattr(property_listings, "_has_listed", lambda db, prop_id: False)
    prop, first = _draft(client, officer)
    second = _create(client, officer, prop["id"]).json()
    _move(client, officer, first["id"], "listed")
    resp = _move(client, officer, second["id"], "listed")
    assert resp.status_code == 409
    rows = client.get(f"{API}/properties/{prop['id']}/listings", headers=bearer(officer["accessToken"])).json()
    assert sorted(r["status"] for r in rows) == ["draft", "listed"]


def test_other_institution_and_unknown_are_identical_404(client, officer):
    _, lst = _draft(client, officer)
    other = _second_officer(client)
    for call in (
        lambda i: _move(client, other, i, "listed"),
        lambda i: _patch(client, other, i, {"description": "x"}),
    ):
        cross, unknown = call(lst["id"]), call(MISSING)
        assert cross.status_code == unknown.status_code == 404
        assert cross.json() == unknown.json()
    assert _move(client, officer, lst["id"], "listed").status_code == 200  # untouched by the other officer


def test_buyer_and_anonymous_rejected(client, officer):
    _, lst = _draft(client, officer)
    buyer = _buyer_token(client)
    url = _lurl(lst["id"])
    assert client.post(f"{url}/transition", json={"to": "listed"}).status_code == 401
    assert client.patch(url, json={"description": "x"}).status_code == 401
    assert client.post(f"{url}/transition", json={"to": "listed"}, headers=bearer(buyer)).status_code == 403
    assert client.patch(url, json={"description": "x"}, headers=bearer(buyer)).status_code == 403


def test_patch_edits_marketing_fields_in_draft_and_listed(client, officer):
    _, lst = _draft(client, officer)
    resp = _patch(client, officer, lst["id"], {"askingPrice": "400000.50", "bedrooms": 4, "description": "New"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert float(body["askingPrice"]) == 400000.5 and body["bedrooms"] == 4 and body["description"] == "New"
    assert body["squareFeet"] == BODY["squareFeet"] and body["status"] == "draft"
    _move(client, officer, lst["id"], "listed")
    assert _patch(client, officer, lst["id"], {"bathrooms": "3.0"}).status_code == 200


def test_patch_can_clear_optional_field(client, officer):
    _, lst = _draft(client, officer)
    assert _patch(client, officer, lst["id"], {"description": None}).json()["description"] is None


@pytest.mark.parametrize(
    "body",
    [{}, {"askingPrice": "0"}, {"askingPrice": None}, {"bedrooms": -1}, {"bathrooms": "-1"}, {"squareFeet": 0},
     {"status": "listed"}, {"id": "x"}, {"listedAt": "2026-01-01T00:00:00Z"}],
)  # fmt: skip
def test_patch_validation(client, officer, body):
    _, lst = _draft(client, officer)
    assert _patch(client, officer, lst["id"], body).status_code == 422


def test_patch_withdrawn_is_409(client, officer):
    _, lst = _draft(client, officer)
    _move(client, officer, lst["id"], "withdrawn")
    resp = _patch(client, officer, lst["id"], {"description": "x"})
    assert resp.status_code == 409


def test_patch_sold_is_409(client, officer, session_factory):
    import uuid

    from app.models import PropertyListing

    _, lst = _draft(client, officer)
    with session_factory() as db:
        db.get(PropertyListing, uuid.UUID(lst["id"])).status = "sold"
        db.commit()
    assert _patch(client, officer, lst["id"], {"description": "x"}).status_code == 409
