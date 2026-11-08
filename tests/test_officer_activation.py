import uuid
from datetime import UTC, datetime, timedelta

import jwt

from tests.conftest import STRONG_PASSWORD
from tests.test_signup_rate_limit import MAX_SIGNUPS

API = "/api/v1"
EMAIL = "newofficer@example.com"
NEW_PASSWORD = "BrandNew456!"


def _pending_officer(client, officer, session_factory, email=EMAIL):
    """An institution user as later steps will create them: unusable placeholder hash, passwordSetAt unset."""
    from app.models import InstitutionUser
    from app.services.auth import issue_institution_invite_token, unusable_password_hash

    db = session_factory()
    try:
        row = InstitutionUser(
            institutionId=uuid.UUID(officer["institution"]["id"]),
            name="New Officer",
            email=email,
            role="loan_officer",
            passwordHash=unusable_password_hash(),
        )
        db.add(row)
        db.commit()
        return row.id, issue_institution_invite_token(db, row.id)
    finally:
        db.close()


def _activate(client, token, password=NEW_PASSWORD):
    return client.post(f"{API}/auth/institution/activate", json={"token": token, "password": password})


def _login(client, password=NEW_PASSWORD, email=EMAIL):
    return client.post(f"{API}/auth/institution/login", json={"email": email, "password": password})


def _signed(session_factory, claims):
    from app.services.auth import ensure_secret_state

    db = session_factory()
    try:
        return jwt.encode(claims, ensure_secret_state(db).currentSecret, algorithm="HS256")
    finally:
        db.close()


def test_activation_sets_password_and_allows_login(client, officer, session_factory):
    _, token = _pending_officer(client, officer, session_factory)
    assert _login(client).status_code == 401  # the placeholder never lets anyone in
    resp = _activate(client, token)
    assert resp.status_code == 200, resp.text
    assert resp.json()["tokenType"] == "Bearer"
    assert _login(client).status_code == 200
    assert _login(client, "WrongPass123!").status_code == 401


def test_activation_token_is_single_use(client, officer, session_factory):
    _, token = _pending_officer(client, officer, session_factory)
    assert _activate(client, token).status_code == 200
    assert _activate(client, token, "Another789!x").status_code == 401
    assert _login(client).status_code == 200  # the first password still stands
    assert _login(client, "Another789!x").status_code == 401


def test_fresh_token_for_activated_officer_is_rejected(client, officer, session_factory):
    from app.services.auth import issue_institution_invite_token

    uid, token = _pending_officer(client, officer, session_factory)
    assert _activate(client, token).status_code == 200
    db = session_factory()
    again = issue_institution_invite_token(db, uid)
    db.close()
    assert _activate(client, again, "Another789!x").status_code == 401


def test_token_for_existing_officer_with_password_is_rejected(client, officer, session_factory):
    from app.services.auth import issue_institution_invite_token

    db = session_factory()
    token = issue_institution_invite_token(db, uuid.UUID(officer["institutionUser"]["id"]))
    db.close()
    assert _activate(client, token, "Another789!x").status_code == 401
    ok = client.post(f"{API}/auth/institution/login", json={"email": "casey@example.com", "password": STRONG_PASSWORD})
    assert ok.status_code == 200


def test_bootstrap_officer_has_password_set_but_created_user_is_pending(client, officer, session_factory):
    from app.models import InstitutionUser

    created = _create(client, officer)
    assert created.status_code == 201, created.text
    db = session_factory()
    rows = {r.email: r for r in db.query(InstitutionUser).all()}
    assert rows["casey@example.com"].passwordSetAt is not None
    assert rows[EMAIL].passwordSetAt is None
    db.close()


def _create(client, officer, **extra):
    return client.post(
        f"{API}/institution-users",
        json={"institutionId": officer["institution"]["id"], "name": "Second", "email": EMAIL, **extra},
        headers={"Authorization": f"Bearer {officer['accessToken']}"},
    )


def test_create_returns_activation_token_that_activates(client, officer):
    created = _create(client, officer)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["activationPath"] == f"/activate#token={body['activationToken']}"
    assert "passwordHash" not in body and "password" not in body
    assert _login(client).status_code == 401  # cannot log in before activation
    assert _activate(client, body["activationToken"]).status_code == 200
    assert _login(client).status_code == 200


def test_create_rejects_a_password_field(client, officer):
    resp = _create(client, officer, password=STRONG_PASSWORD)
    assert resp.status_code == 422
    assert _login(client, STRONG_PASSWORD).status_code == 401


def test_expired_activation_token_is_rejected(client, officer, session_factory):
    uid, _ = _pending_officer(client, officer, session_factory)
    past = datetime.now(UTC) - timedelta(days=1)
    expired = _signed(
        session_factory,
        {
            "sub": str(uid),
            "userType": "institution_invite",
            "iat": int((past - timedelta(days=7)).timestamp()),
            "exp": int(past.timestamp()),
        },
    )
    assert _activate(client, expired).status_code == 401


def test_other_token_types_are_not_activation_tokens(client, officer, session_factory):
    from app.services.auth import issue_invite_token, issue_token

    uid, _ = _pending_officer(client, officer, session_factory)
    db = session_factory()
    wrong = [
        issue_token(db, uid, "institution_user"),  # valid signature, same subject: only userType can reject it
        issue_invite_token(db, uid),  # the owner invite token
    ]
    db.close()
    for token in wrong:
        assert _activate(client, token).status_code == 401
    assert _login(client).status_code == 401


def test_malformed_token_is_rejected(client, officer):
    assert _activate(client, "not-a-jwt").status_code == 401


def test_token_for_unknown_or_malformed_subject_is_generic_401(client, officer, session_factory):
    now = datetime.now(UTC)
    for sub in (str(uuid.uuid4()), "not-a-uuid"):
        token = _signed(
            session_factory,
            {
                "sub": sub,
                "userType": "institution_invite",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(days=1)).timestamp()),
            },
        )
        assert _activate(client, token).status_code == 401


def test_weak_password_is_rejected_and_token_stays_usable(client, officer, session_factory):
    from app.models import InstitutionUser

    _, token = _pending_officer(client, officer, session_factory)
    assert _activate(client, token, "weak").status_code == 400
    db = session_factory()
    assert db.query(InstitutionUser).filter(InstitutionUser.email == EMAIL).one().passwordSetAt is None
    db.close()
    assert _activate(client, token).status_code == 200


def test_activation_is_limited_per_ip_with_its_own_budget(client):
    for _ in range(MAX_SIGNUPS):
        assert _activate(client, "garbage").status_code == 401
    blocked = _activate(client, "garbage")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # Independent of the accept-invite budget.
    other = client.post(f"{API}/auth/accept-invite", json={"token": "garbage", "password": STRONG_PASSWORD})
    assert other.status_code == 401
