from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app


@compiles(UUID, "sqlite")
def _uuid_as_char_on_sqlite(type_, compiler, **kw):
    # The models use postgresql.UUID; SQLite would declare the column "UUID" (NUMERIC affinity) and coerce ids that
    # look like numbers (e.g. 32 digits with one 'e') into floats. CHAR(32) has TEXT affinity and matches the stored
    # hex.
    return "CHAR(32)"


STRONG_PASSWORD = "ValidPass123!"
BOOTSTRAP_TOKEN = "test-setup-token"
BOOTSTRAP_HEADERS = {"X-Bootstrap-Token": BOOTSTRAP_TOKEN}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """Freeze token timestamps (JWT iat is stored server-side and rotates every request).

    Without this, a test that reuses a token across calls fails whenever the wall clock crosses a second
    boundary between them. Starts 60 s in the past: PyJWT rejects a token whose iat is in the real future, and
    its exp must stay valid, so tests may advance this clock by up to ~60 s but no further.
    """
    state = {"now": datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=60)}
    monkeypatch.setattr("app.services.auth.now_utc_seconds", lambda: state["now"])
    return state


@pytest.fixture(autouse=True)
def bootstrap_token(monkeypatch):
    """Bootstrap is gated by a setup token; tests that send BOOTSTRAP_HEADERS get through, others are rejected."""
    monkeypatch.setattr("app.api.routes.auth.settings.bootstrap_token", BOOTSTRAP_TOKEN)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Deliberately not used as a context manager: that would run startup hooks
    # (secret-rotation loop) bound to the real Postgres session.
    yield TestClient(app)
    app.dependency_overrides.clear()


def bootstrap_officer(client, institution_name, officer_name, officer_email, admin_headers=None):
    """Bootstrap an institution and activate its first officer (bootstrap gives no session, only an activation link).
    Bootstrap needs a signed-in platform admin: pass `admin_headers`, or one is created here (named after the officer
    email so several institutions can be bootstrapped in one test). Returns the bootstrap body plus the activated
    officer's `accessToken`, so callers keep their old shape."""
    if admin_headers is None:
        # The client fixture's get_db override yields a session on the test database.
        session_factory = contextmanager(app.dependency_overrides[get_db])
        admin_headers = make_platform_admin(client, session_factory, f"root-{officer_email}")
    resp = client.post(
        "/api/v1/auth/institution/bootstrap",
        json={"institutionName": institution_name, "officerName": officer_name, "officerEmail": officer_email},
        headers={**admin_headers, **BOOTSTRAP_HEADERS},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    activated = client.post(
        "/api/v1/auth/institution/activate", json={"token": body["activationToken"], "password": STRONG_PASSWORD}
    )
    assert activated.status_code == 200, activated.text
    return {**body, "accessToken": activated.json()["accessToken"]}


def sign_in_officer(client, clock, email, password=STRONG_PASSWORD):
    """Sign an officer in the way the product now requires: password, then the authenticator. A first sign-in enrols
    through the enrolment challenge (enroll-start, then enroll-confirm with a real code). Returns the LoginResponse
    body plus `totpSecret`. Works once per officer: a second sign-in would need a code from a newer time step."""
    import pyotp

    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    challenge = resp.json()
    assert challenge.get("enrolmentRequired") is True, challenge
    token = challenge["challengeToken"]
    started = client.post("/api/v1/auth/login/totp/enroll-start", json={"challengeToken": token})
    assert started.status_code == 200, started.text
    secret = started.json()["secret"]
    code = pyotp.TOTP(secret).at(clock["now"])
    done = client.post("/api/v1/auth/login/totp/enroll-confirm", json={"challengeToken": token, "code": code})
    assert done.status_code == 200, done.text
    return {**done.json(), "totpSecret": secret}


@pytest.fixture()
def officer(client):
    """Bootstrap and activate an institution; returns the response body plus accessToken (password STRONG_PASSWORD)."""
    return bootstrap_officer(client, "Atlas Lending", "Casey Officer", "casey@example.com")


def make_platform_admin(client, session_factory, email="root@example.com"):
    """Create a platform admin the way the operator script does (invite link), set its password through the
    accept-invite endpoint and return (auth headers, accessToken). Password is STRONG_PASSWORD."""
    from app.services.auth import create_platform_admin  # imported here so unrelated tests never need it

    with session_factory() as db:
        invite = create_platform_admin(db, email)
    resp = client.post("/api/v1/auth/accept-invite", json={"token": invite, "password": STRONG_PASSWORD})
    assert resp.status_code == 200, resp.text
    token = resp.json()["accessToken"]
    return bearer(token)


@pytest.fixture()
def platform_admin(client, session_factory):
    """Auth headers ({"Authorization": "Bearer ..."}) of a signed-in platform admin. Send them together with
    BOOTSTRAP_HEADERS to reach POST /auth/institution/bootstrap: `headers={**platform_admin, **BOOTSTRAP_HEADERS}`."""
    return make_platform_admin(client, session_factory)
