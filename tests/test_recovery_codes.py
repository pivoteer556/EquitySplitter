"""One-time recovery codes for officers who lost their authenticator (2l step 3b)."""

import re

import pytest
from sqlalchemy import select

from app.models import RecoveryCode
from tests.conftest import STRONG_PASSWORD, bearer

LOGIN = "/api/v1/auth/login"
LOGIN_TOTP = "/api/v1/auth/login/totp"
START = "/api/v1/auth/login/totp/enroll-start"
CONFIRM = "/api/v1/auth/login/totp/enroll-confirm"
EMAIL = "casey@example.com"
FORMAT = re.compile(r"^[A-Z2-9]{5}-[A-Z2-9]{5}$")


def _enrol(client, clock):
    import pyotp

    token = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()["challengeToken"]
    secret = client.post(START, json={"challengeToken": token}).json()["secret"]
    code = pyotp.TOTP(secret).at(clock["now"])
    return token, secret, client.post(CONFIRM, json={"challengeToken": token, "code": code})


@pytest.fixture
def codes(client, officer, clock):
    resp = _enrol(client, clock)[2]
    assert resp.status_code == 200, resp.text
    return resp.json()["recoveryCodes"]


def _challenge(client):
    resp = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert resp.json()["secondFactorRequired"] is True
    return resp.json()["challengeToken"]


def _use(client, code, token=None):
    return client.post(LOGIN_TOTP, json={"challengeToken": token or _challenge(client), "code": code})


def test_enrol_confirm_returns_eight_distinct_well_formed_codes_with_the_normal_response(client, officer, clock):
    resp = _enrol(client, clock)[2]
    body = resp.json()
    assert body["accessToken"] and body["userType"] == "institution_user"
    assert len(body["recoveryCodes"]) == 8 and len(set(body["recoveryCodes"])) == 8
    assert all(FORMAT.match(c) for c in body["recoveryCodes"])


def test_only_hashes_are_stored(client, officer, clock, session_factory):
    codes = _enrol(client, clock)[2].json()["recoveryCodes"]
    with session_factory() as db:
        rows = db.scalars(select(RecoveryCode)).all()
    assert len(rows) == 8 and all(r.usedAt is None for r in rows)
    stored = " ".join(r.codeHash for r in rows)
    for c in codes:
        assert c not in stored and c.replace("-", "") not in stored


def test_a_recovery_code_completes_sign_in_and_is_then_spent(client, officer, codes):
    resp = _use(client, codes[0])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["userType"] == "institution_user" and body["role"] == "loan_officer"
    assert client.get("/api/v1/listings", headers=bearer(body["accessToken"])).status_code == 200
    again = _use(client, codes[0])
    assert again.status_code == 401 and again.json() == {"detail": "Invalid credentials"}
    assert _use(client, codes[1]).status_code == 200  # the others still work


def test_case_whitespace_and_dash_variations_are_accepted(client, officer, codes):
    raw = codes[0].replace("-", "")
    assert _use(client, f"  {raw.lower()[:5]} {raw.lower()[5:]} ").status_code == 200
    assert _use(client, codes[1].replace("-", "").lower()).status_code == 200


def test_wrong_recovery_code_is_the_generic_401(client, officer, codes):
    resp = _use(client, "AAAAA-AAAAA")
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}


def test_wrong_recovery_codes_share_the_login_rate_limit(client, officer, codes):
    token = _challenge(client)
    statuses = [_use(client, "AAAAA-AAAAA", token).status_code for _ in range(6)]
    assert statuses[:5] == [401] * 5 and statuses[5] == 429
    assert _use(client, codes[0], token).status_code == 429  # locked out: even a valid code is refused


def test_a_used_recovery_code_counts_against_the_limit(client, officer, codes):
    token = _challenge(client)
    assert _use(client, codes[0], token).status_code == 200  # success resets the budget
    statuses = [_use(client, codes[0], token).status_code for _ in range(6)]
    assert statuses[:5] == [401] * 5 and statuses[5] == 429


def test_malformed_codes_are_still_rejected(client, officer, codes):
    token = _challenge(client)
    for bad in ["", "12345", "1234567", "abcdef", "ABCDE-FGHJK-LMNPQ-RSTUV", "!!!!!-!!!!!"]:
        assert _use(client, bad, token).status_code == 422, bad


def test_recovery_codes_do_not_work_at_enrol_confirm(client, officer, clock):
    token, _, first = _enrol(client, clock)
    code = first.json()["recoveryCodes"][0]
    fresh = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()
    # An enrolled officer gets a code challenge, so enrol-confirm refuses regardless of the code.
    assert client.post(CONFIRM, json={"challengeToken": fresh["challengeToken"], "code": code}).status_code == 422
    assert client.post(CONFIRM, json={"challengeToken": token, "code": "123456"}).status_code == 401


def test_recovery_code_cannot_skip_enrolment(client, officer):
    # An officer who has not enrolled has no codes; the enrolment challenge cannot redeem the second step either.
    token = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()["challengeToken"]
    assert _use(client, "AAAAA-AAAAA", token).status_code == 401


def test_garbage_and_access_tokens_cannot_redeem_a_recovery_code(client, officer, codes):
    assert _use(client, codes[0], "garbage").status_code == 401
    assert _use(client, codes[0], officer["accessToken"]).status_code == 401


def test_a_pending_restart_of_enrolment_does_not_mint_codes_until_confirmed(client, officer, clock):
    token = client.post(LOGIN, json={"email": EMAIL, "password": STRONG_PASSWORD}).json()["challengeToken"]
    client.post(START, json={"challengeToken": token})
    client.post(START, json={"challengeToken": token})
    assert _use(client, "AAAAA-AAAAA", token).status_code == 401
