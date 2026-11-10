"""One-time recovery codes for officers who lost their authenticator (2l step 3b)."""

import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import RecoveryCode
from tests.conftest import STRONG_PASSWORD, bearer, sign_in_officer

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


# --- 2l step 3c: an authenticated officer regenerates their codes -------------------------------------------------

REGEN = "/api/v1/auth/institution/totp/recovery-codes"


@pytest.fixture
def signed_in(client, officer, clock):
    """A bearer-signed-in officer with a confirmed authenticator and their first 8 codes."""
    body = sign_in_officer(client, clock, EMAIL)
    return {"headers": bearer(body["accessToken"]), "secret": body["totpSecret"], "codes": body["recoveryCodes"]}


def _next_code(secret, clock):
    import pyotp

    return pyotp.TOTP(secret).at(clock["now"] + timedelta(seconds=30))  # the enrol step is spent; use the next one


def _regen(client, signed_in, clock, code=None):
    code = code or _next_code(signed_in["secret"], clock)
    return client.post(REGEN, json={"code": code}, headers=signed_in["headers"])


def test_regenerate_returns_eight_fresh_codes_and_kills_all_old_ones(client, signed_in, clock, session_factory):
    old = signed_in["codes"]
    assert _use(client, old[0]).status_code == 200  # one old code is already used
    resp = _regen(client, signed_in, clock)
    assert resp.status_code == 200, resp.text
    new = resp.json()["recoveryCodes"]
    assert len(new) == 8 and len(set(new)) == 8 and all(FORMAT.match(c) for c in new)
    assert not set(new) & set(old)
    with session_factory() as db:
        rows = db.scalars(select(RecoveryCode)).all()
    assert len(rows) == 8 and all(r.usedAt is None for r in rows)  # used and unused old rows are gone
    token = _challenge(client)
    for c in old[:4]:  # stay under the 5-failure limit
        r = _use(client, c, token)
        assert r.status_code == 401 and r.json() == {"detail": "Invalid credentials"}
    assert _use(client, new[0]).status_code == 200


def test_wrong_code_is_401_leaves_codes_untouched_and_counts(client, signed_in, clock, session_factory):
    resp = _regen(client, signed_in, clock, "000000")
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}
    with session_factory() as db:
        assert len(db.scalars(select(RecoveryCode)).all()) == 8
    assert _use(client, signed_in["codes"][0]).status_code == 200  # old codes still work
    statuses = [_regen(client, signed_in, clock, "000000").status_code for _ in range(6)]
    assert statuses[:5] == [401] * 5 and statuses[5] == 429  # the successful login above reset the budget


def test_replayed_totp_step_is_refused(client, signed_in, clock):
    code = _next_code(signed_in["secret"], clock)
    assert _regen(client, signed_in, clock, code).status_code == 200
    assert _regen(client, signed_in, clock, code).status_code == 401


def test_the_enrolment_step_code_is_a_replay(client, signed_in, clock):
    import pyotp

    assert _regen(client, signed_in, clock, pyotp.TOTP(signed_in["secret"]).at(clock["now"])).status_code == 401


def test_a_recovery_code_is_not_accepted_here(client, signed_in, clock):
    resp = client.post(REGEN, json={"code": signed_in["codes"][0]}, headers=signed_in["headers"])
    assert resp.status_code == 422


def test_five_failures_then_429_with_retry_after_shared_with_login(client, signed_in, clock):
    token = _challenge(client)
    statuses = [_regen(client, signed_in, clock, "000000").status_code for _ in range(5)]
    assert statuses == [401] * 5
    locked = _regen(client, signed_in, clock)
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) > 0
    assert _use(client, signed_in["codes"][0], token).status_code == 429  # the login budget is the same bucket


def test_login_failures_count_toward_the_regenerate_budget(client, signed_in, clock):
    token = _challenge(client)
    assert [_use(client, "AAAAA-AAAAA", token).status_code for _ in range(5)] == [401] * 5
    assert _regen(client, signed_in, clock).status_code == 429


def test_officer_without_a_confirmed_authenticator_gets_the_generic_refusal(client, officer, clock):
    resp = client.post(REGEN, json={"code": "123456"}, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}
    # a pending (unconfirmed) enrolment is the same
    import pyotp

    headers = bearer(officer["accessToken"])
    secret = client.post("/api/v1/auth/institution/totp/enroll", headers=headers).json()["secret"]
    resp = client.post(REGEN, json={"code": pyotp.TOTP(secret).at(clock["now"])}, headers=headers)
    assert resp.status_code == 401 and resp.json() == {"detail": "Invalid credentials"}


def test_requires_a_valid_officer_bearer(client, signed_in):
    assert client.post(REGEN, json={"code": "123456"}).status_code == 401
    assert client.post(REGEN, json={"code": "123456"}, headers=bearer("garbage")).status_code == 401
