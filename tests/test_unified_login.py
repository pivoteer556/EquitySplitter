"""One POST /auth/login signs in every kind of account and says which kind it was."""

from app.models import InstitutionUser, User
from app.services.auth import hash_password
from tests.conftest import STRONG_PASSWORD, make_platform_admin

LOGIN = "/api/v1/auth/login"
OFFICER_LOGIN = "/api/v1/auth/institution/login"
MAX_FAILURES = 5


def _login(client, email, password=STRONG_PASSWORD, url=LOGIN):
    return client.post(url, json={"email": email, "password": password})


def _register_owner(client, email="sam@example.com"):
    client.post("/api/v1/auth/register", json={"name": "Sam", "email": email, "password": STRONG_PASSWORD})


def test_officer_signs_in_with_access_info(client, officer):
    resp = _login(client, "casey@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokenType"] == "Bearer"
    assert body["userType"] == "institution_user"
    assert body["isPlatformAdmin"] is False
    assert body["role"] == "loan_officer"
    assert body["institutionId"] == officer["institution"]["id"]



def test_owner_signs_in_as_user(client):
    _register_owner(client)
    body = _login(client, "sam@example.com").json()
    assert body["userType"] == "user"
    assert body["isPlatformAdmin"] is False
    assert body["role"] is None
    assert body["institutionId"] is None


def test_platform_admin_is_flagged(client, session_factory):
    make_platform_admin(client, session_factory, "root@example.com")
    body = _login(client, "root@example.com").json()
    assert body["userType"] == "user"
    assert body["isPlatformAdmin"] is True


def test_every_failure_is_the_same_401(client, officer):
    _register_owner(client)
    responses = [
        _login(client, "nobody@example.com", "WrongPass123!"),
        _login(client, "sam@example.com", "WrongPass123!"),
        _login(client, "casey@example.com", "WrongPass123!"),
    ]
    assert [r.status_code for r in responses] == [401, 401, 401]
    assert all(r.json() == {"detail": "Invalid credentials"} for r in responses)


def test_sixth_failure_is_429_and_correct_password_is_refused(client, officer):
    for _ in range(MAX_FAILURES):
        assert _login(client, "casey@example.com", "WrongPass123!").status_code == 401  # one failure counts once
    blocked = _login(client, "casey@example.com", "WrongPass123!")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert _login(client, "casey@example.com").status_code == 429


def test_alternating_endpoints_share_one_budget(client, officer):
    for i in range(MAX_FAILURES):
        url = LOGIN if i % 2 == 0 else OFFICER_LOGIN
        assert _login(client, "casey@example.com", "WrongPass123!", url).status_code == 401
    assert _login(client, "casey@example.com", "WrongPass123!", LOGIN).status_code == 429
    assert _login(client, "casey@example.com", "WrongPass123!", OFFICER_LOGIN).status_code == 429


def _same_email_owner_and_officer(session_factory, officer):
    with session_factory() as db:
        db.add(User(name="Casey Owner", email="casey@example.com", passwordHash=hash_password("OwnerPass123!x")))
        db.commit()


def test_email_in_both_kinds_user_first_then_officer(client, officer, session_factory):
    _same_email_owner_and_officer(session_factory, officer)
    assert _login(client, "casey@example.com", "OwnerPass123!x").json()["userType"] == "user"
    # the officer's password is wrong for the user account, so the officer account is tried
    assert _login(client, "casey@example.com", STRONG_PASSWORD).json()["userType"] == "institution_user"


def test_password_matching_both_signs_in_as_user(client, officer, session_factory):
    with session_factory() as db:
        db.add(User(name="Casey Owner", email="casey@example.com", passwordHash=hash_password(STRONG_PASSWORD)))
        db.commit()
        assert db.query(InstitutionUser).count() == 1
    assert _login(client, "casey@example.com").json()["userType"] == "user"
