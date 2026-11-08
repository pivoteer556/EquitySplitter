from uuid import UUID

from app.models import InstitutionUser
from app.services.auth import unusable_password_hash
from tests.conftest import STRONG_PASSWORD, bearer
from tests.test_accept_invite import _invited
from tests.test_listings import _buyer_token, _third_officer
from tests.test_property_list import _second_officer

API = "/api/v1"
URL = f"{API}/professionals"
KEYS = {"id", "name", "role", "institutionName"}


def _add(client, officer, name, email, role):
    """Create an institution user as `officer`; returns (response, officer's rotated token)."""
    resp = client.post(
        f"{API}/institution-users",
        json={
            "institutionId": officer["institution"]["id"],
            "name": name,
            "email": email,
            "password": STRONG_PASSWORD,
            "role": role,
        },
        headers=bearer(officer["accessToken"]),
    )
    officer["accessToken"] = resp.headers.get("X-Refreshed-Token", officer["accessToken"])
    return resp


def _get(client, token, params=""):
    resp = client.get(URL + params, headers=bearer(token))
    return resp, resp.headers.get("X-Refreshed-Token", token)


def _seed(client, officer):
    other = _second_officer(client)
    assert _add(client, officer, "Una Underwriter", "una@example.com", "underwriter").status_code == 201
    assert _add(client, other, "Bo Broker", "bobroker@example.com", "broker").status_code == 201
    return other


def test_buyer_sees_professionals_from_two_institutions_with_only_four_keys(client, officer):
    _seed(client, officer)
    resp, _ = _get(client, _buyer_token(client))
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 4  # two bootstrap officers + two added
    for item in items:
        assert set(item) == KEYS
    assert {i["institutionName"] for i in items} == {"Atlas Lending", "Borealis Bank"}
    for forbidden in ("@example.com", "passwordHash", "institutionId", "lastTokenIssuedAt", "createdAt"):
        assert forbidden not in resp.text


def test_id_is_the_institution_users_id(client, officer):
    resp, _ = _get(client, _buyer_token(client))
    assert [i["id"] for i in resp.json()] == [officer["institutionUser"]["id"]]


def test_officer_can_browse_too(client, officer):
    third = _third_officer(client)
    _seed(client, officer)
    resp, _ = _get(client, third["accessToken"])
    assert resp.status_code == 200 and len(resp.json()) == 5


def test_role_filter_and_unknown_role(client, officer):
    _seed(client, officer)
    token = _buyer_token(client)
    resp, token = _get(client, token, "?role=underwriter")
    assert [i["name"] for i in resp.json()] == ["Una Underwriter"]
    resp, token = _get(client, token, "?role=loan_officer")
    assert {i["name"] for i in resp.json()} == {"Casey Officer", "Bo Officer"}
    resp, token = _get(client, token, "?role=janitor")
    assert resp.status_code == 422


def test_non_vocabulary_role_is_not_listed(client, officer, session_factory):
    db = session_factory()
    db.add(
        InstitutionUser(
            institutionId=UUID(officer["institution"]["id"]),
            name="Legacy Janitor",
            email="janitor@example.com",
            passwordHash=unusable_password_hash(),
            role="janitor",
        )
    )
    db.commit()
    db.close()
    resp, _ = _get(client, _buyer_token(client))
    assert [i["name"] for i in resp.json()] == ["Casey Officer"]


def test_creating_user_validates_role(client, officer):
    assert _add(client, officer, "Jan", "jan@example.com", "janitor").status_code == 422
    assert _add(client, officer, "Una", "una@example.com", "underwriter").status_code == 201
    assert _add(client, officer, "Bro", "bro@example.com", "broker").status_code == 201
    default = client.post(
        f"{API}/institution-users",
        json={
            "institutionId": officer["institution"]["id"],
            "name": "Def",
            "email": "def@example.com",
            "password": STRONG_PASSWORD,
        },
        headers=bearer(officer["accessToken"]),
    )
    assert default.status_code == 201 and default.json()["role"] == "loan_officer"


def test_auth_required(client, officer):
    _prop, invite = _invited(client, officer)
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=bearer("not-a-jwt")).status_code == 401
    assert client.get(URL, headers=bearer(invite)).status_code == 403


def test_order_limit_offset(client, officer):
    _seed(client, officer)
    token = _buyer_token(client)
    full, token = _get(client, token)
    items = full.json()
    assert items == sorted(items, key=lambda i: (i["name"], i["id"]))
    assert [i["name"] for i in items] == ["Bo Broker", "Bo Officer", "Casey Officer", "Una Underwriter"]
    page, token = _get(client, token, "?limit=2&offset=1")
    assert page.json() == items[1:3]
    for bad in ("?limit=0", "?limit=201", "?offset=-1"):
        resp, token = _get(client, token, bad)
        assert resp.status_code == 422
