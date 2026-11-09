"""Second sign-in step for officers with a confirmed authenticator (2l step 2)."""

import pyotp
import pytest

from tests.conftest import STRONG_PASSWORD, bearer

LOGIN = "/api/v1/auth/login"
LOGIN_TOTP = "/api/v1/auth/login/totp"
ENROLL = "/api/v1/auth/institution/totp/enroll"
CONFIRM = "/api/v1/auth/institution/totp/confirm"
EMAIL = "casey@example.com"


def _code(secret, clock, offset=0):
    return pyotp.TOTP(secret).at(clock["now"], counter_offset=offset)


def _wrong(secret, clock):
    return "000000" if _code(secret, clock) != "000000" else "111111"


@pytest.fixture
def enrolled(client, officer, clock):
    """The officer with a confirmed credential; returns the base32 secret. Confirming uses the current step, so
    sign-in tests use offset +1 (inside the window) to get a code newer than lastUsedStep."""
    secret = client.post(ENROLL, headers=bearer(officer["accessToken"])).json()["secret"]
    headers = bearer(officer["accessToken"])
    assert client.post(CONFIRM, json={"code": _code(secret, clock)}, headers=headers).status_code == 204
    return secret


def _password_step(client):
    return client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD})


def _challenge(client):
    resp = _password_step(client)
    assert resp.status_code == 200, resp.text
    return resp.json()["challengeToken"]


def test_password_alone_no_longer_signs_in_an_officer_with_an_authenticator(client, enrolled):
    body = _password_step(client).json()
    assert body["userType"] == "institution_user"
    assert body["secondFactorRequired"] is True
    assert body["challengeToken"]
    assert "accessToken" not in body


def test_correct_code_completes_sign_in_with_the_normal_login_response(client, officer, enrolled, clock):
    resp = client.post(
        LOGIN_TOTP, json={"challengeToken": _challenge(client), "code": _code(enrolled, clock, 1)}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["userType"] == "institution_user" and body["isPlatformAdmin"] is False
    assert body["role"] == "loan_officer" and body["institutionId"] == officer["institution"]["id"]
    # The issued token is a real session.
    assert client.post(CONFIRM, json={"code": "123456"}, headers=bearer(body["accessToken"])).status_code in (400, 409)


def test_wrong_code_is_the_generic_401(client, enrolled, clock):
    resp = client.post(LOGIN_TOTP, json={"challengeToken": _challenge(client), "code": _wrong(enrolled, clock)})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid credentials"}


def test_a_used_code_cannot_be_replayed(client, enrolled, clock):
    code = _code(enrolled, clock, 1)
    assert client.post(LOGIN_TOTP, json={"challengeToken": _challenge(client), "code": code}).status_code == 200
    again = client.post(LOGIN_TOTP, json={"challengeToken": _challenge(client), "code": code})
    assert again.status_code == 401 and again.json() == {"detail": "Invalid credentials"}
    # The code used to confirm enrolment (an earlier step) is dead too.
    old = client.post(LOGIN_TOTP, json={"challengeToken": _challenge(client), "code": _code(enrolled, clock)})
    assert old.status_code == 401


def test_wrong_codes_share_the_login_rate_limit(client, enrolled, clock):
    wrong = _wrong(enrolled, clock)
    token = _challenge(client)
    statuses = [client.post(LOGIN_TOTP, json={"challengeToken": token, "code": wrong}).status_code for _ in range(6)]
    assert statuses[:5] == [401] * 5 and statuses[5] == 429
    # Locked out: the right code is refused, and so is the password step (same per-ip+email budget).
    assert client.post(LOGIN_TOTP, json={"challengeToken": token, "code": _code(enrolled, clock, 1)}).status_code == 429
    assert _password_step(client).status_code == 429


def test_a_challenge_token_is_never_an_access_token(client, enrolled):
    token = _challenge(client)
    for path in ["/api/v1/auth/institution/totp/enroll", "/api/v1/auth/institution/revoke"]:
        assert client.post(path, json={}, headers=bearer(token)).status_code in (401, 403), path
    assert client.get("/api/v1/listings", headers=bearer(token)).status_code in (401, 403)


def test_an_access_or_garbage_token_is_not_a_challenge(client, officer, enrolled, clock):
    code = _code(enrolled, clock, 1)
    for bad in [officer["accessToken"], "garbage"]:
        resp = client.post(LOGIN_TOTP, json={"challengeToken": bad, "code": code})
        assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}


def test_malformed_code_is_rejected(client, enrolled):
    token = _challenge(client)
    for bad in ["", "12345", "1234567", "abcdef"]:
        assert client.post(LOGIN_TOTP, json={"challengeToken": token, "code": bad}).status_code == 422, bad


def test_officer_without_a_confirmed_credential_signs_in_as_before(client, officer):
    body = _password_step(client).json()
    assert body["accessToken"] and "challengeToken" not in body and "secondFactorRequired" not in body


def test_pending_unconfirmed_enrolment_does_not_trigger_the_second_step(client, officer):
    client.post(ENROLL, headers=bearer(officer["accessToken"]))
    assert "accessToken" in _password_step(client).json()


def test_plain_user_signs_in_as_before(client):
    client.post("/api/v1/auth/register", json={"name": "Bea", "email": "bea@example.com", "password": STRONG_PASSWORD})
    body = client.post(LOGIN, json={"email": "bea@example.com", "password": STRONG_PASSWORD}).json()
    assert body["userType"] == "user" and body["accessToken"] and "challengeToken" not in body


def test_wrong_password_for_an_enrolled_officer_is_still_the_generic_401(client, enrolled):
    resp = client.post(LOGIN, json={"email": EMAIL, "password": "Wrong-Pass123!"})
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}
