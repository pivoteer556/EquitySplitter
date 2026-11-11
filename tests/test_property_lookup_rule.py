"""ONE rule for every route that takes a property id (or a listing id, which is owned through its property):
malformed or unknown id -> 404 "Property not found", a property the caller may not touch -> 403 (an officer of another
institution, a buyer not linked to it), and the property's own officer/owner is never turned away by the lookup.
State rules (active property, 409s, agreement missing) are not ownership checks and are tested elsewhere."""

import pytest

from tests.conftest import bearer
from tests.test_accept_invite import _invited
from tests.test_connection_requests import _buyer
from tests.test_property_flow import _property
from tests.test_property_list import _owner_token, _second_officer

API = "/api/v1"
AGREEMENT = {"noticeDays": 30, "valuationMethod": "appraisal", "partialClaimMethod": "pro_rata"}
LISTING = {"askingPrice": "350000.00"}
OFFICER, BOTH, BUYER = "officer", "both", "buyer"
OFFICER_DENIED = "Loan officer not authorized for institution"

# (method, path, body, who may call the route). {p} is a property id, {l} a listing id.
ROUTES = [
    ("GET", "/properties/{p}", None, BOTH),
    ("PATCH", "/properties/{p}", {"address": "2 Elm St"}, OFFICER),
    ("DELETE", "/properties/{p}", None, OFFICER),
    ("GET", "/properties/{p}/owners", None, BOTH),
    ("POST", "/properties/{p}/agreement", AGREEMENT, OFFICER),
    ("POST", "/properties/{p}/owners", {"name": "New Owner", "email": "new@example.com"}, OFFICER),
    ("POST", "/properties/{p}/acknowledge", None, BUYER),
    ("POST", "/properties/{p}/listings", LISTING, OFFICER),
    ("GET", "/properties/{p}/listings", None, OFFICER),
    ("PATCH", "/property-listings/{l}", {"description": "x"}, OFFICER),
    ("POST", "/property-listings/{l}/transition", {"to": "withdrawn"}, OFFICER),
]
IDS = [f"{m} {p}" for m, p, _, _ in ROUTES]


def _call(client, route, token, prop_id="", listing_id=""):
    method, path, body, _ = route
    url = API + path.replace("{p}", prop_id).replace("{l}", listing_id)
    return client.request(method, url, json=body, headers=bearer(token))


@pytest.fixture()
def world(client, officer):
    """A property with a listing and a linked owner (institution A), plus officer B and an unlinked buyer."""
    prop = _property(client, officer)
    url = f"{API}/properties/{prop['id']}/listings"
    listing = client.post(url, json=LISTING, headers=bearer(officer["accessToken"]))
    assert listing.status_code == 201, listing.text
    other = _second_officer(client)
    return {"prop": prop["id"], "listing": listing.json()["id"], "officer": officer, "other": other["accessToken"]}


def _callers(route, world, client):
    """(label, token) pairs for the callers a route accepts."""
    who = route[3]
    callers = []
    if who in (OFFICER, BOTH):
        callers.append(("officer", world["other"]))
    if who in (BUYER, BOTH):
        callers.append(("buyer", _buyer(client).token))
    return callers


@pytest.mark.parametrize("route", ROUTES, ids=IDS)
@pytest.mark.parametrize("bad_id", ["00000000-0000-4000-8000-000000000000", "not-a-uuid"], ids=["unknown", "malformed"])
def test_unknown_or_malformed_id_is_404(client, world, route, bad_id):
    for label, token in _callers(route, world, client):
        resp = _call(client, route, token, prop_id=bad_id, listing_id=bad_id)
        assert (resp.status_code, resp.json()["detail"]) == (404, "Property not found"), (label, resp.text)


@pytest.mark.parametrize("route", ROUTES, ids=IDS)
def test_property_of_another_institution_or_unlinked_buyer_is_403(client, world, route):
    for label, token in _callers(route, world, client):
        resp = _call(client, route, token, prop_id=world["prop"], listing_id=world["listing"])
        assert resp.status_code == 403, (label, resp.text)
        if label == "officer":
            assert resp.json()["detail"] == OFFICER_DENIED


OFFICER_ROUTES = [r for r in ROUTES if r[3] != BUYER]


@pytest.mark.parametrize("route", OFFICER_ROUTES, ids=[f"{r[0]} {r[1]}" for r in OFFICER_ROUTES])
def test_the_properties_own_officer_is_not_turned_away(client, world, route):
    resp = _call(client, route, world["officer"]["accessToken"], prop_id=world["prop"], listing_id=world["listing"])
    detail = resp.json().get("detail") if resp.status_code in (403, 404) else None
    assert detail not in ("Property not found", OFFICER_DENIED), resp.text


def test_a_linked_owner_is_not_turned_away(client, officer):
    prop, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    for path in (f"/properties/{prop['id']}", f"/properties/{prop['id']}/owners"):
        assert client.get(API + path, headers=bearer(token)).status_code == 200
    resp = client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(token))
    assert resp.status_code == 200, resp.text

