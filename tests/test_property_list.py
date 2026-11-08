from datetime import UTC, datetime

from app.models import Property
from app.schemas.property import PropertyRead
from tests.conftest import bearer, bootstrap_officer
from tests.test_accept_invite import _invited
from tests.test_property_flow import _agreement, _property

API = "/api/v1"
URL = f"{API}/properties"


def _second_officer(client):
    return bootstrap_officer(client, "Borealis Bank", "Bo Officer", "bo@example.com")


def _owner_token(client, invite_token, email="owner@example.com"):
    password = "BrandNew456!"
    assert (
        client.post(f"{API}/auth/accept-invite", json={"token": invite_token, "password": password}).status_code == 200
    )
    return client.post(f"{API}/auth/login", json={"email": email, "password": password}).json()["accessToken"]


def _ids(resp):
    assert resp.status_code == 200, resp.text
    return [p["id"] for p in resp.json()]


def test_officer_sees_only_own_institution(client, officer):
    other = _second_officer(client)
    mine = _property(client, officer)
    theirs = _property(client, other)
    assert _ids(client.get(URL, headers=bearer(officer["accessToken"]))) == [mine["id"]]
    assert _ids(client.get(URL, headers=bearer(other["accessToken"]))) == [theirs["id"]]


def test_owner_sees_only_linked_properties(client, officer):
    linked, invite = _invited(client, officer)
    _property(client, officer)  # same institution, owner not linked
    token = _owner_token(client, invite)
    assert _ids(client.get(URL, headers=bearer(token))) == [linked["id"]]


def test_owner_does_not_see_other_institution(client, officer):
    other = _second_officer(client)
    _property(client, other)
    linked, invite = _invited(client, officer)
    token = _owner_token(client, invite)
    assert _ids(client.get(URL, headers=bearer(token))) == [linked["id"]]


def test_unauthenticated_is_401(client):
    assert client.get(URL).status_code == 401


def test_garbage_token_is_401(client, officer):
    assert client.get(URL, headers=bearer("not-a-jwt")).status_code == 401


def test_invite_token_is_rejected_like_other_routes(client, officer):
    prop, invite = _invited(client, officer)
    assert client.get(URL, headers=bearer(invite)).status_code == 403
    assert client.get(f"{URL}/{prop['id']}", headers=bearer(invite)).status_code == 403


def _seed_times(session_factory, ids_in_order):
    # Oldest first: ids_in_order[0] gets the earliest createdAt.
    db = session_factory()
    for day, pid in enumerate(ids_in_order, start=1):
        db.query(Property).filter(Property.id == pid).one().createdAt = datetime(2026, 1, day, tzinfo=UTC)
    db.commit()
    db.close()


def test_ordering_limit_and_offset(client, officer, session_factory):
    from uuid import UUID

    ids = [_property(client, officer)["id"] for _ in range(3)]
    _seed_times(session_factory, [UUID(i) for i in ids])
    headers = bearer(officer["accessToken"])
    assert _ids(client.get(URL, headers=headers)) == ids[::-1]  # newest first
    headers = bearer(client.get(URL, headers=headers).headers["X-Refreshed-Token"])
    first = client.get(URL, params={"limit": 2}, headers=headers)
    assert _ids(first) == ids[::-1][:2]
    headers = bearer(first.headers["X-Refreshed-Token"])
    assert _ids(client.get(URL, params={"limit": 2, "offset": 2}, headers=headers)) == ids[::-1][2:]


def test_pagination_params_are_validated(client, officer):
    headers = bearer(officer["accessToken"])
    for params in ({"limit": 0}, {"limit": 201}, {"offset": -1}):
        assert client.get(URL, params=params, headers=headers).status_code == 422
        headers = bearer(client.get(URL, headers=headers).headers["X-Refreshed-Token"])


def test_response_shape_is_property_read(client, officer):
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    resp = client.get(URL, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 200
    assert set(resp.json()[0]) == set(PropertyRead.model_fields)
