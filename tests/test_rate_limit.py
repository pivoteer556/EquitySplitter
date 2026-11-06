from datetime import datetime, timedelta, timezone

import pytest

from app.models import RateLimitHit
from app.services.rate_limit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


@pytest.fixture()
def db(session_factory):
    session = session_factory()
    yield session
    session.close()


def make(max_attempts=3, window=60):
    clock = FakeClock()
    return RateLimiter(max_attempts, window, clock), clock


def test_blocks_after_max_attempts(db):
    limiter, _ = make()
    for _ in range(2):
        limiter.record_attempt(db, "a")
    assert limiter.retry_after(db, "a") == 0
    limiter.record_attempt(db, "a")
    assert limiter.retry_after(db, "a") == 60


def test_window_expiry_unblocks(db):
    limiter, clock = make()
    for _ in range(3):
        limiter.record_attempt(db, "a")
    clock.advance(59)
    assert limiter.retry_after(db, "a") == 1
    clock.advance(1)
    assert limiter.retry_after(db, "a") == 0


def test_reset_clears_attempts(db):
    limiter, _ = make()
    for _ in range(3):
        limiter.record_attempt(db, "a")
    limiter.reset(db, "a")
    assert limiter.retry_after(db, "a") == 0


def test_keys_are_independent(db):
    limiter, _ = make()
    for _ in range(3):
        limiter.record_attempt(db, "a")
    assert limiter.retry_after(db, "a") > 0
    assert limiter.retry_after(db, "b") == 0


def test_state_is_shared_between_limiter_instances(db):
    # Two instances stand in for two replicas (or one process before and after a restart).
    first, clock = make()
    second = RateLimiter(3, 60, clock)
    for _ in range(3):
        first.record_attempt(db, "a")
    assert second.retry_after(db, "a") == 60


def test_expired_rows_are_pruned_and_raw_key_is_not_stored(db):
    limiter, clock = make()
    limiter.record_attempt(db, "victim@example.com")
    assert "victim@example.com" not in db.query(RateLimitHit.key).scalar()
    clock.advance(61)
    limiter.record_attempt(db, "someone-else")
    assert db.query(RateLimitHit).count() == 1
