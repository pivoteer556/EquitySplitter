import re

import pytest

from scripts.create_platform_admin import main
from tests.conftest import STRONG_PASSWORD

EMAIL = "root@example.com"
LINK = re.compile(r"/accept-invite#token=(\S+)")


def _run(session_factory, capsys, email=EMAIL):
    code = main([email], session_factory)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_prints_link_that_sets_password_then_signin_works(client, session_factory, capsys):
    code, out, _ = _run(session_factory, capsys)
    assert code == 0
    token = LINK.search(out).group(1)
    accepted = client.post("/api/v1/auth/accept-invite", json={"token": token, "password": STRONG_PASSWORD})
    assert accepted.status_code == 200, accepted.text
    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert login.status_code == 200, login.text


def test_script_takes_and_prints_no_password(session_factory, capsys):
    with pytest.raises(SystemExit):
        main([EMAIL, "--password", "x"], session_factory)
    capsys.readouterr()
    _, out, err = _run(session_factory, capsys)
    assert "password" not in (out + err).lower().replace("set-password", "").replace("set a password", "")


def test_rerun_reissues_link_and_does_not_change_password(client, session_factory, capsys):
    _run(session_factory, capsys)
    code, out, _ = _run(session_factory, capsys)
    token = LINK.search(out).group(1)
    client.post("/api/v1/auth/accept-invite", json={"token": token, "password": STRONG_PASSWORD})
    code, out, err = _run(session_factory, capsys)
    assert code == 0 and LINK.search(out)
    # The password chosen above still works; a re-run never replaced it.
    assert client.post("/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD}).status_code == 200
    # And a stale link cannot reset it (single use).
    stale = LINK.search(out).group(1)
    again = client.post("/api/v1/auth/accept-invite", json={"token": stale, "password": "Other123!xyz"})
    assert again.status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": EMAIL, "password": STRONG_PASSWORD}).status_code == 200


def test_refuses_to_promote_an_existing_ordinary_account(client, session_factory, capsys):
    client.post("/api/v1/auth/register", json={"name": "Bea", "email": EMAIL, "password": STRONG_PASSWORD})
    code, out, err = _run(session_factory, capsys)
    assert code != 0 and not LINK.search(out)
