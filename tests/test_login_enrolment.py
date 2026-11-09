"""Enrolment at first sign-in for officers without a confirmed authenticator (2l step 3)."""

import pyotp
import pytest

from tests.conftest import STRONG_PASSWORD, bearer

LOGIN = "/api/v1/auth/login"
LOGIN_TOTP = "/api/v1/auth/login/totp"
START = "/api/v1/auth/login/totp/enroll-start"
CONFIRM = "/api/v1/auth/login/totp/enroll-confirm"
EMAIL = "casey@example.com"


def _code(secret, clock, offset=0):
    return pyotp.TOTP(secret).at(clock["now"], counter_offset=offset)


def _wrong(secret, clock):
    return "000000" if _code(secret, clock) != "000000" else "111111"


@pytest.fixture
def challenge(client, officer):
    resp = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["challengeToken"]


@pytest.fixture
def secret(client, challenge):
    return client.post(START, json={"challengeToken": challenge}).json()["secret"]


def test_password_alone_does_not_sign_in_an_unenrolled_officer(client, officer):
    body = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()
    assert body["userType"] == "institution_user"
    assert body["enrolmentRequired"] is True
    assert body["challengeToken"]
    assert "accessToken" not in body and "secondFactorRequired" not in body


def test_enrol_start_returns_secret_and_uri(client, challenge):
    resp = client.post(START, json={"challengeToken": challenge})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["secret"] and body["otpauthUri"].startswith("otpauth://totp/")
    assert body["secret"] in body["otpauthUri"]


def test_enrol_start_replaces_a_pending_credential(client, challenge, clock):
    first = client.post(START, json={"challengeToken": challenge}).json()["secret"]
    second = client.post(START, json={"challengeToken": challenge}).json()["secret"]
    assert first != second
    resp = client.post(CONFIRM, json={"challengeToken": challenge, "code": _code(first, clock)})
    assert resp.status_code == 401


def test_enrol_confirm_returns_the_normal_login_response(client, officer, challenge, secret, clock):
    resp = client.post(CONFIRM, json={"challengeToken": challenge, "code": _code(secret, clock)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["userType"] == "institution_user" and body["isPlatformAdmin"] is False
    assert body["role"] == "loan_officer" and body["institutionId"] == officer["institution"]["id"]
    assert client.get("/api/v1/listings", headers=bearer(body["accessToken"])).status_code == 200


def test_after_enrolment_login_asks_for_the_code_and_the_enrol_code_is_spent(client, challenge, secret, clock):
    code = _code(secret, clock)
    assert client.post(CONFIRM, json={"challengeToken": challenge, "code": code}).status_code == 200
    body = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()
    assert body["secondFactorRequired"] is True and "enrolmentRequired" not in body
    again = client.post(LOGIN_TOTP, json={"challengeToken": body["challengeToken"], "code": code})
    assert again.status_code == 401  # replay of the enrolment code
    ok = client.post(LOGIN_TOTP, json={"challengeToken": body["challengeToken"], "code": _code(secret, clock, 1)})
    assert ok.status_code == 200


def test_wrong_code_is_generic_401_and_leaves_enrolment_unconfirmed(client, challenge, secret, clock):
    resp = client.post(CONFIRM, json={"challengeToken": challenge, "code": _wrong(secret, clock)})
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}
    assert client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()["enrolmentRequired"] is True


def test_wrong_codes_share_the_login_rate_limit(client, challenge, secret, clock):
    wrong = _wrong(secret, clock)
    statuses = [
        client.post(CONFIRM, json={"challengeToken": challenge, "code": wrong}).status_code for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5 and statuses[5] == 429
    assert client.post(CONFIRM, json={"challengeToken": challenge, "code": _code(secret, clock)}).status_code == 429
    assert client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).status_code == 429


def test_malformed_code_is_rejected(client, challenge, secret):
    for bad in ["", "12345", "1234567", "abcdef"]:
        assert client.post(CONFIRM, json={"challengeToken": challenge, "code": bad}).status_code == 422, bad


def test_enrolment_and_code_challenges_are_not_interchangeable(client, officer, challenge, secret, clock):
    # An enrolment challenge cannot redeem the code step.
    resp = client.post(LOGIN_TOTP, json={"challengeToken": challenge, "code": _code(secret, clock)})
    assert resp.status_code == 401
    # Enrol, then take the code challenge: it cannot enrol or start enrolment.
    client.post(CONFIRM, json={"challengeToken": challenge, "code": _code(secret, clock)})
    code_challenge = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()["challengeToken"]
    assert client.post(START, json={"challengeToken": code_challenge}).status_code == 401
    body = {"challengeToken": code_challenge, "code": _code(secret, clock, 1)}
    assert client.post(CONFIRM, json=body).status_code == 401


def test_enrolment_challenge_is_never_an_access_token(client, challenge):
    for path in ["/api/v1/auth/institution/totp/enroll", "/api/v1/auth/institution/revoke"]:
        assert client.post(path, json={}, headers=bearer(challenge)).status_code in (401, 403), path
    assert client.get("/api/v1/listings", headers=bearer(challenge)).status_code in (401, 403)


def test_garbage_or_access_tokens_are_not_enrolment_challenges(client, officer, secret, clock):
    for bad in [officer["accessToken"], "garbage"]:
        assert client.post(START, json={"challengeToken": bad}).status_code == 401
        resp = client.post(CONFIRM, json={"challengeToken": bad, "code": _code(secret, clock)})
        assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}


def test_an_already_enrolled_officer_cannot_use_the_enrolment_path(client, officer, challenge, secret, clock):
    # The enrolment challenge was issued while unenrolled; enrol through the bearer path meanwhile.
    headers = bearer(officer["accessToken"])
    s = client.post("/api/v1/auth/institution/totp/enroll", headers=headers).json()["secret"]
    confirm = client.post("/api/v1/auth/institution/totp/confirm", json={"code": _code(s, clock)}, headers=headers)
    assert confirm.status_code == 204
    assert client.post(START, json={"challengeToken": challenge}).status_code == 401
    resp = client.post(CONFIRM, json={"challengeToken": challenge, "code": _code(s, clock, 1)})
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}


def test_plain_user_signs_in_as_before(client):
    client.post("/api/v1/auth/register", json={"name": "Bea", "email": "bea@example.com", "password": STRONG_PASSWORD})
    body = client.post(LOGIN, json={"email": "bea@example.com", "password": STRONG_PASSWORD}).json()
    assert body["userType"] == "user" and body["accessToken"] and "enrolmentRequired" not in body


def test_the_legacy_officer_login_no_longer_hands_out_a_token(client, officer):
    resp = client.post("/api/v1/auth/institution/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert resp.status_code in (404, 410)
