import uuid

from app.models import AuthSecretState
from app.services.auth import now_utc_seconds


def test_uuid_that_looks_like_a_number_survives_sqlite_round_trip(session_factory):
    # Regression for an intermittent CI failure: postgresql.UUID is declared "UUID" in SQLite DDL, which has NUMERIC
    # affinity, so a random id whose 32 hex chars are all digits (optionally one 'e') was stored as REAL/inf.
    db = session_factory()
    state = AuthSecretState(id=uuid.UUID("1" * 20 + "e" + "9" * 11), currentSecret="x", rotatedAt=now_utc_seconds())
    db.add(state)
    db.commit()
    db.refresh(state)
    assert state.id == uuid.UUID("1" * 20 + "e" + "9" * 11)
    db.close()
