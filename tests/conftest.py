from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app

STRONG_PASSWORD = "ValidPass123!"


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


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
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


@pytest.fixture()
def officer(client):
    """Bootstrap an institution; returns the response body (accessToken, institution, institutionUser)."""
    resp = client.post(
        "/api/v1/auth/institution/bootstrap",
        json={
            "institutionName": "Atlas Lending",
            "officerName": "Casey Officer",
            "officerEmail": "casey@example.com",
            "officerPassword": STRONG_PASSWORD,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
