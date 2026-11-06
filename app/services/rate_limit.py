"""Database-backed attempt limiter (sliding window), keyed by an arbitrary string.

Seam for callers: retry_after(db, key) before doing the work, record_attempt(db, key) for each
counted attempt, reset(db, key) on success. State lives in the `rateLimitHits` table, so it is shared
by every replica and survives restarts. Known limit: concurrent requests can slip a few attempts past
the threshold because check and record are separate statements (acceptable for brute-force throttling).
"""
import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import RateLimitHit


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo; values are always stored as UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, clock: Callable[[], datetime] = _utcnow):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock  # injectable so tests need no sleeping

    @staticmethod
    def _digest(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def retry_after(self, db: Session, key: str) -> int:
        """Seconds until `key` may try again; 0 when not blocked."""
        now = self._clock()
        expiries = list(
            db.scalars(
                select(RateLimitHit.expiresAt)
                .where(RateLimitHit.key == self._digest(key), RateLimitHit.expiresAt > now)
                .order_by(RateLimitHit.expiresAt)
            )
        )
        if len(expiries) < self.max_attempts:
            return 0
        # Unblocked once enough of the oldest attempts have expired to drop below the threshold.
        unblock_at = _as_utc(expiries[len(expiries) - self.max_attempts])
        return max(1, int((unblock_at - now).total_seconds() + 0.999))

    def record_attempt(self, db: Session, key: str) -> None:
        now = self._clock()
        db.execute(delete(RateLimitHit).where(RateLimitHit.expiresAt <= now))  # prune everyone's expired rows
        db.add(RateLimitHit(id=uuid.uuid4(), key=self._digest(key), expiresAt=now + timedelta(seconds=self.window_seconds)))
        db.commit()

    def reset(self, db: Session, key: str) -> None:
        db.execute(delete(RateLimitHit).where(RateLimitHit.key == self._digest(key)))
        db.commit()


# Shared limiters. Stateless objects; the counts live in the database.
login_limiter = RateLimiter(max_attempts=5, window_seconds=60)  # failed logins per scope+IP+email
signup_limiter = RateLimiter(max_attempts=10, window_seconds=3600)  # every signup attempt per IP
