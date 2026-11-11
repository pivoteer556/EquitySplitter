from uuid import uuid4

import pytest

from tests.conftest import STRONG_PASSWORD, bearer
from tests.test_accept_invite import _invited
from tests.test_property_flow import _agreement, _property
from tests.test_property_list import _owner_token, _second_officer

API = "/api/v1"
EDITABLE = ("address", "loanAmount", "currentBalance", "monthlyPayment", "dynamicBillingEnabled")


class Session:
    """Carries the rotating bearer token across calls."""

    def __init__(self, client, token):
        self.client, self.token = client, token

    def call(self, method, prop_id, **kwargs):
        resp = self.client.request(method, f"{API}/properties/{prop_id}", headers=bearer(self.token), **kwargs)
        self.token = resp.headers.get("X-Refreshed-Token", self.token)
        return resp

    def patch(self, prop_id, body):
        return self.call("PATCH", prop_id, json=body)

    def read(self, prop_id):
        resp = self.call("GET", prop_id)
        assert resp.status_code == 200, resp.text
        return resp.json()["property"]


@pytest.fixture
def setup(client, officer):
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])  # GET detail 500s on a property without an agreement (pre-existing)
    return Session(client, officer["accessToken"]), prop


def test_update_one_field_leaves_others(setup):
    s, prop = setup
    resp = s.patch(prop["id"], {"address": "2 Elm St"})
    assert resp.status_code == 200, resp.text
    after = s.read(prop["id"])
    assert after["address"] == "2 Elm St"
    assert {k: v for k, v in after.items() if k != "address"} == {k: v for k, v in prop.items() if k != "address"}
    assert resp.json() == after


def test_update_several_fields(setup):
    s, prop = setup
    body = {"loanAmount": "400000", "currentBalance": "0", "monthlyPayment": "2000", "dynamicBillingEnabled": True}
    assert s.patch(prop["id"], body).status_code == 200
    after = s.read(prop["id"])
    assert float(after["loanAmount"]) == 400000
    assert float(after["currentBalance"]) == 0
    assert float(after["monthlyPayment"]) == 2000
    assert after["dynamicBillingEnabled"] is True
    assert after["address"] == prop["address"]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "active"},
        {"institutionId": str(uuid4())},
        {"id": str(uuid4())},
        {"createdAt": "2020-01-01T00:00:00Z"},
        {"address": "ok", "status": "active"},
    ],
)
def test_immutable_fields_rejected(setup, body):
    s, prop = setup
    assert s.patch(prop["id"], body).status_code == 422
    assert s.read(prop["id"]) == prop


@pytest.mark.parametrize(
    "body",
    [
        {"loanAmount": "-1"},
        {"loanAmount": "0"},
        {"currentBalance": "-1"},
        {"monthlyPayment": "0"},
        {"address": ""},
        {"address": ["x"]},
        {"loanAmount": "abc"},
        {"dynamicBillingEnabled": "maybe"},
        {"address": None},
        {"loanAmount": None},
        {"address": "fine", "monthlyPayment": "-5"},
    ],
)
def test_invalid_values_rejected(setup, body):
    s, prop = setup
    assert s.patch(prop["id"], body).status_code == 422
    assert s.read(prop["id"]) == prop


def test_empty_body_rejected(setup):
    s, prop = setup
    assert s.patch(prop["id"], {}).status_code == 422
    assert s.read(prop["id"]) == prop


def test_active_property_is_locked(client, officer):
    prop, invite = _invited(client, officer)
    owner = _owner_token(client, invite)
    ack = client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(owner))
    assert ack.status_code == 200
    s = Session(client, officer["accessToken"])
    before = s.read(prop["id"])
    assert before["status"] == "active"
    resp = s.patch(prop["id"], {"address": "Nope"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Property is active; setup writes are closed"
    assert s.read(prop["id"]) == before


def test_other_institution_is_forbidden_missing_is_404(client, officer):
    other = _second_officer(client)
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    s = Session(client, other["accessToken"])
    real = s.patch(prop["id"], {"address": "Hijack"})
    missing = s.patch(str(uuid4()), {"address": "Hijack"})
    assert (real.status_code, real.json()) == (403, {"detail": "Loan officer not authorized for institution"})
    assert (missing.status_code, missing.json()) == (404, {"detail": "Property not found"})
    assert Session(client, officer["accessToken"]).read(prop["id"])["address"] == prop["address"]


def test_owner_forbidden_and_auth_failures(client, officer):
    prop, invite = _invited(client, officer)
    url = f"{API}/properties/{prop['id']}"
    body = {"address": "X"}
    assert client.patch(url, json=body).status_code == 401
    assert client.patch(url, json=body, headers=bearer("not-a-jwt")).status_code == 401
    assert client.patch(url, json=body, headers=bearer(invite)).status_code == 403
    registered = client.post(
        f"{API}/auth/register", json={"name": "S", "email": "s@example.com", "password": STRONG_PASSWORD}
    ).json()["accessToken"]
    assert client.patch(url, json=body, headers=bearer(registered)).status_code == 403
    owner = _owner_token(client, invite)
    assert client.patch(url, json=body, headers=bearer(owner)).status_code == 403
