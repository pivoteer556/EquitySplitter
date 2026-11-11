from uuid import uuid4

import pytest

from tests.conftest import STRONG_PASSWORD, bearer
from tests.test_accept_invite import _invited
from tests.test_property_flow import _agreement, _property
from tests.test_property_list import _owner_token, _second_officer

API = "/api/v1"
ROUTES = ("{base}", "{base}/owners")


def _urls(prop_id):
    return [r.format(base=f"{API}/properties/{prop_id}") for r in ROUTES]


def _get(client, token, url):
    """GET and return (response, next token): tokens rotate on every authenticated call."""
    resp = client.get(url, headers=bearer(token))
    return resp, resp.headers.get("X-Refreshed-Token", token)


def test_officer_reads_detail_of_own_property(client, officer):
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    resp, _ = _get(client, officer["accessToken"], _urls(prop["id"])[0])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["property"]["id"] == prop["id"]
    assert body["property"]["address"] == "1 Main St"
    assert body["agreement"]["noticeDays"] == 30


def test_officer_reads_owners_of_own_property(client, officer):
    prop, _invite = _invited(client, officer)
    resp, _ = _get(client, officer["accessToken"], _urls(prop["id"])[1])
    assert resp.status_code == 200, resp.text
    assert [o["email"] for o in resp.json()["owners"]] == ["owner@example.com"]


@pytest.mark.parametrize("route", [0, 1])
def test_other_institution_is_forbidden_missing_is_404(client, officer, route):
    other = _second_officer(client)
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    real, token = _get(client, other["accessToken"], _urls(prop["id"])[route])
    missing, _ = _get(client, token, _urls(uuid4())[route])
    assert (real.status_code, real.json()) == (403, {"detail": "Loan officer not authorized for institution"})
    assert (missing.status_code, missing.json()) == (404, {"detail": "Property not found"})


@pytest.mark.parametrize("route", [0, 1])
def test_linked_owner_still_reads(client, officer, route):
    prop, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    resp, _ = _get(client, token, _urls(prop["id"])[route])
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("route", [0, 1])
def test_unlinked_owner_still_403_and_missing_404(client, officer, route):
    prop, _invite = _invited(client, officer)
    token = client.post(
        f"{API}/auth/register", json={"name": "S", "email": "s@example.com", "password": STRONG_PASSWORD}
    ).json()["accessToken"]
    resp, token = _get(client, token, _urls(prop["id"])[route])
    assert resp.status_code == 403
    missing, _ = _get(client, token, _urls(uuid4())[route])
    assert missing.status_code == 404


@pytest.mark.parametrize("route", [0, 1])
def test_unauthenticated_and_invite_tokens(client, officer, route):
    prop, invite = _invited(client, officer)
    url = _urls(prop["id"])[route]
    assert client.get(url).status_code == 401
    assert client.get(url, headers=bearer("not-a-jwt")).status_code == 401
    assert client.get(url, headers=bearer(invite)).status_code == 403
