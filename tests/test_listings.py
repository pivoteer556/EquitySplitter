import json

from tests.conftest import STRONG_PASSWORD, bearer
from tests.test_accept_invite import _invited
from tests.test_property_flow import _agreement, _property
from tests.test_property_list import _owner_token, _second_officer

API = "/api/v1"
URL = f"{API}/listings"
LOAN = "412345.67"
KEYS = {"id", "address", "status", "createdAt"}


def _third_officer(client):
    resp = client.post(
        f"{API}/auth/institution/bootstrap",
        json={
            "institutionName": "Cirrus Credit",
            "officerName": "Ci Officer",
            "officerEmail": "ci@example.com",
            "officerPassword": STRONG_PASSWORD,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _buyer_token(client):
    resp = client.post(
        f"{API}/auth/register", json={"name": "Buyer", "email": "buyer@example.com", "password": STRONG_PASSWORD}
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["accessToken"]


def _priced_property(client, officer, address):
    resp = client.post(
        f"{API}/properties",
        json={
            "institutionId": officer["institution"]["id"],
            "address": address,
            "loanAmount": LOAN,
            "currentBalance": "250000",
            "monthlyPayment": "1800",
        },
        headers=bearer(officer["accessToken"]),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _get(client, token, params=""):
    resp = client.get(URL + params, headers=bearer(token))
    return resp, resp.headers.get("X-Refreshed-Token", token)


def test_buyer_sees_pending_listings_from_two_institutions(client, officer):
    other = _second_officer(client)
    a = _priced_property(client, officer, "A St")
    b = _priced_property(client, other, "B St")
    resp, _ = _get(client, _buyer_token(client))
    assert resp.status_code == 200, resp.text
    assert {i["id"] for i in resp.json()} == {a["id"], b["id"]}


def test_officer_of_third_institution_sees_listings(client, officer):
    other = _second_officer(client)
    third = _third_officer(client)
    a = _priced_property(client, officer, "A St")
    b = _priced_property(client, other, "B St")
    resp, _ = _get(client, third["accessToken"])
    assert resp.status_code == 200, resp.text
    assert {i["id"] for i in resp.json()} == {a["id"], b["id"]}


def test_active_property_is_not_listed(client, officer):
    active, invite = _invited(client, officer)
    pending = _priced_property(client, officer, "Pending St")
    token = _owner_token(client, invite)
    assert client.post(f"{API}/properties/{active['id']}/acknowledge", headers=bearer(token)).status_code == 200
    resp, _ = _get(client, _buyer_token(client))
    assert [i["id"] for i in resp.json()] == [pending["id"]]


def test_listing_exposes_only_restricted_fields(client, officer):
    prop, _invite = _invited(client, officer)  # has an agreement and an owner@example.com owner
    _priced_property(client, officer, "Priced St")
    resp, _ = _get(client, _buyer_token(client))
    items = resp.json()
    assert len(items) == 2
    for item in items:
        assert set(item) == KEYS
        assert item["status"] == "pending_acknowledgement"
    text = json.dumps(items) + resp.text
    for forbidden in (LOAN, "owner@example.com", "loanAmount", "institutionId", "noticeDays"):
        assert forbidden not in text


def test_auth_required(client, officer):
    _prop, invite = _invited(client, officer)
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=bearer("not-a-jwt")).status_code == 401
    assert client.get(URL, headers=bearer(invite)).status_code == 403


def test_order_limit_offset_and_no_agreement(client, officer):
    for n in range(3):
        _priced_property(client, officer, f"{n} Row St")  # none has an agreement
    _agreement(client, officer, _property(client, officer)["id"])
    token = _buyer_token(client)
    full, token = _get(client, token)
    items = full.json()
    assert len(items) == 4
    expected = sorted(sorted(items, key=lambda i: i["id"]), key=lambda i: i["createdAt"], reverse=True)
    assert items == expected
    page, token = _get(client, token, "?limit=2&offset=1")
    assert page.json() == items[1:3]
    for bad in ("?limit=0", "?limit=201", "?offset=-1"):
        resp, token = _get(client, token, bad)
        assert resp.status_code == 422
