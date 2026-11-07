from tests.conftest import STRONG_PASSWORD, bearer

API = "/api/v1"


def _property(client, officer):
    resp = client.post(
        f"{API}/properties",
        json={
            "institutionId": officer["institution"]["id"],
            "address": "1 Main St",
            "loanAmount": "300000",
            "currentBalance": "250000",
            "monthlyPayment": "1800",
        },
        headers=bearer(officer["accessToken"]),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _agreement(client, officer, prop_id):
    return client.post(
        f"{API}/properties/{prop_id}/agreement",
        json={"noticeDays": 30, "valuationMethod": "appraisal", "partialClaimMethod": "pro_rata"},
        headers=bearer(officer["accessToken"]),
    )


def test_create_property_starts_pending(client, officer):
    assert _property(client, officer)["status"] == "pending_acknowledgement"


def test_property_for_other_institution_is_forbidden(client, officer):
    resp = client.post(
        f"{API}/properties",
        json={
            "institutionId": "00000000-0000-0000-0000-000000000009",
            "address": "x",
            "loanAmount": "1",
            "currentBalance": "0",
            "monthlyPayment": "1",
        },
        headers=bearer(officer["accessToken"]),
    )
    assert resp.status_code == 403


def test_agreement_only_once(client, officer):
    prop = _property(client, officer)
    assert _agreement(client, officer, prop["id"]).status_code == 201
    assert _agreement(client, officer, prop["id"]).status_code == 409


def test_invite_owner_requires_agreement(client, officer):
    prop = _property(client, officer)
    resp = client.post(
        f"{API}/properties/{prop['id']}/owners",
        json={"name": "Owner", "email": "owner@example.com"},
        headers=bearer(officer["accessToken"]),
    )
    assert resp.status_code == 400


def test_property_activates_when_all_owners_acknowledge(client, officer):
    prop = _property(client, officer)
    assert _agreement(client, officer, prop["id"]).status_code == 201
    invite = client.post(
        f"{API}/properties/{prop['id']}/owners",
        json={"name": "Owner", "email": "owner@example.com", "maxOwnershipPercent": "50"},
        headers=bearer(officer["accessToken"]),
    )
    assert invite.status_code == 201
    # Re-inviting is idempotent.
    again = client.post(
        f"{API}/properties/{prop['id']}/owners",
        json={"name": "Owner", "email": "owner@example.com"},
        headers=bearer(officer["accessToken"]),
    )
    assert again.json()["id"] == invite.json()["id"]

    # The invited owner has no password; they set one with the invite token the officer hands over.
    accepted = client.post(
        f"{API}/auth/accept-invite", json={"token": invite.json()["inviteToken"], "password": STRONG_PASSWORD}
    )
    assert accepted.status_code == 200, accepted.text

    token = client.post(f"{API}/auth/login", json={"email": "owner@example.com", "password": STRONG_PASSWORD}).json()[
        "accessToken"
    ]
    ack = client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(token))
    assert ack.status_code == 200
    assert ack.json()["signedAt"] is not None

    # Tokens rotate on each use; read the property back with the refreshed one.
    token = ack.headers["X-Refreshed-Token"]
    detail = client.get(f"{API}/properties/{prop['id']}", headers=bearer(token))
    assert detail.status_code == 200
    assert detail.json()["property"]["status"] == "active"

    # Setup writes are closed once active.
    assert _agreement(client, officer, prop["id"]).status_code in (403, 409)


def test_non_owner_cannot_read_or_acknowledge(client, officer):
    prop = _property(client, officer)
    _agreement(client, officer, prop["id"])
    token = client.post(
        f"{API}/auth/register", json={"name": "S", "email": "s@example.com", "password": STRONG_PASSWORD}
    ).json()["accessToken"]
    assert client.post(f"{API}/properties/{prop['id']}/acknowledge", headers=bearer(token)).status_code == 403
    assert client.get(f"{API}/properties/{prop['id']}", headers=bearer(token)).status_code == 403
