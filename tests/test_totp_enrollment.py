"""Authenticator-app (TOTP) enrolment for institution users (2l step 1)."""

import pyotp
import pytest

from app.models import TotpCredential
from tests.conftest import bearer

ENROLL = "/api/v1/auth/institution/totp/enroll"
CONFIRM = "/api/v1/auth/institution/totp/confirm"


def _enroll(client, officer):
    resp = client.post(ENROLL, headers=bearer(officer["accessToken"]))
    assert resp.status_code == 200, resp.text
    return resp


def _code(secret, clock, offset=0):
    return pyotp.TOTP(secret).at(clock["now"], counter_offset=offset)


def _confirm(client, token, code):
    return client.post(CONFIRM, json={"code": code}, headers=bearer(token))


def test_enroll_returns_secret_and_uri_for_an_authenticator_app(client, officer):
    body = _enroll(client, officer).json()
    assert len(body["secret"]) >= 32 and body["secret"].isalnum()
    uri = body["otpauthUri"]
    assert uri.startswith("otpauth://totp/")
    assert "casey%40example.com" in uri and "issuer=EquitySplitter" in uri and f"secret={body['secret']}" in uri


def test_enroll_requires_a_session(client):
    assert client.post(ENROLL).status_code == 401


def test_secret_is_not_stored_in_plaintext(client, officer, session_factory):
    secret = _enroll(client, officer).json()["secret"]
    with session_factory() as db:
        stored = db.query(TotpCredential).one().secretEncrypted
    assert secret not in stored and secret.lower() not in stored.lower()


def test_valid_code_confirms_enrolment(client, officer, session_factory, clock):
    secret = _enroll(client, officer).json()["secret"]
    resp = _confirm(client, officer["accessToken"], _code(secret, clock))
    assert resp.status_code == 204, resp.text
    with session_factory() as db:
        assert db.query(TotpCredential).one().confirmedAt is not None


def test_wrong_code_does_not_confirm(client, officer, session_factory, clock):
    secret = _enroll(client, officer).json()["secret"]
    wrong = "000000" if _code(secret, clock) != "000000" else "111111"
    resp = _confirm(client, officer["accessToken"], wrong)
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid code"}
    with session_factory() as db:
        assert db.query(TotpCredential).one().confirmedAt is None


def test_code_from_far_outside_the_window_is_rejected(client, officer, clock):
    secret = _enroll(client, officer).json()["secret"]
    assert _confirm(client, officer["accessToken"], _code(secret, clock, offset=-5)).status_code == 400


def test_confirm_without_enrolling_is_rejected(client, officer):
    assert _confirm(client, officer["accessToken"], "123456").status_code == 400


def test_malformed_code_is_rejected(client, officer):
    _enroll(client, officer)
    for bad in ["", "12345", "1234567", "abcdef", " 12345"]:
        assert _confirm(client, officer["accessToken"], bad).status_code == 422, bad


def test_enrolling_again_before_confirming_replaces_the_secret(client, officer, clock):
    first = _enroll(client, officer).json()["secret"]
    second = _enroll(client, officer).json()["secret"]
    assert first != second
    assert _confirm(client, officer["accessToken"], _code(first, clock)).status_code == 400
    assert _confirm(client, officer["accessToken"], _code(second, clock)).status_code == 204


def test_cannot_enroll_or_confirm_again_once_confirmed(client, officer, clock):
    secret = _enroll(client, officer).json()["secret"]
    assert _confirm(client, officer["accessToken"], _code(secret, clock)).status_code == 204
    assert client.post(ENROLL, headers=bearer(officer["accessToken"])).status_code == 409
    assert _confirm(client, officer["accessToken"], _code(secret, clock)).status_code == 409


def test_wrong_codes_are_rate_limited(client, officer, clock):
    secret = _enroll(client, officer).json()["secret"]
    wrong = "000000" if _code(secret, clock) != "000000" else "111111"
    statuses = [_confirm(client, officer["accessToken"], wrong).status_code for _ in range(6)]
    assert statuses[:5] == [400] * 5 and statuses[5] == 429
    # Even the right code is refused while locked out.
    assert _confirm(client, officer["accessToken"], _code(secret, clock)).status_code == 429


def test_one_officers_enrolment_is_invisible_to_another(client, officer):
    from tests.conftest import bootstrap_officer

    other = bootstrap_officer(client, "Other Bank", "Olive Other", "olive@example.com")
    secret = _enroll(client, officer).json()["secret"]
    # The other officer has no pending enrolment, so a valid code for the first officer's secret means nothing.
    assert _confirm(client, other["accessToken"], pyotp.TOTP(secret).now()).status_code == 400


def test_buyer_token_is_refused(client):
    reg = client.post(
        "/api/v1/auth/register", json={"name": "Bea", "email": "bea@example.com", "password": "ValidPass123!"}
    )
    assert reg.status_code in (200, 201), reg.text
    assert client.post(ENROLL, headers=bearer(reg.json()["accessToken"])).status_code == 403


@pytest.mark.parametrize("path", [ENROLL, CONFIRM])
def test_unauthenticated_calls_are_refused(client, path):
    assert client.post(path, json={"code": "123456"}).status_code == 401
