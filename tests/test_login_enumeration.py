import pytest

from app.models import InstitutionUser, User
from app.services.auth import unusable_password_hash
from tests.conftest import STRONG_PASSWORD

USER_URL = "/api/v1/auth/login"
INSTITUTION_URL = "/api/v1/auth/institution/login"
MAX_FAILURES = 5


@pytest.fixture()
def accounts(client, officer, session_factory):
    """A registered user and the bootstrapped officer, each with a unusable-hash twin."""
    client.post("/api/v1/auth/register", json={"name": "Sam", "email": "sam@example.com", "password": STRONG_PASSWORD})
    db = session_factory()
    db.add(User(name="Nohash", email="nohash@example.com", passwordHash=unusable_password_hash()))
    db.add(
        InstitutionUser(
            institutionId=db.query(InstitutionUser).one().institutionId,
            name="Nohash",
            email="nohash-officer@example.com",
            passwordHash=unusable_password_hash(),
        )
    )
    db.commit()
    db.close()


CASES = [
    (USER_URL, "sam@example.com", "nohash@example.com"),
    (INSTITUTION_URL, "casey@example.com", "nohash-officer@example.com"),
]


def _post(client, url, email, password="WrongPass123!"):
    return client.post(url, json={"email": email, "password": password})


@pytest.mark.parametrize(("url", "known", "nohash"), CASES)
def test_all_credential_failures_are_indistinguishable(client, accounts, url, known, nohash):
    responses = [
        _post(client, url, "nobody@example.com"),
        _post(client, url, known),
        _post(client, url, nohash),
    ]
    assert [r.status_code for r in responses] == [401, 401, 401]
    assert responses[0].json() == responses[1].json() == responses[2].json() == {"detail": "Invalid credentials"}


@pytest.mark.parametrize(("url", "known", "nohash"), CASES)
def test_unknown_email_failures_are_counted(client, accounts, url, known, nohash):
    for _ in range(MAX_FAILURES):
        assert _post(client, url, "nobody@example.com").status_code == 401
    assert _post(client, url, "nobody@example.com").status_code == 429
