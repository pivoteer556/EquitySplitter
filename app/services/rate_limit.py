"""In-memory failed-attempt limiter (sliding window), keyed by an arbitrary string.

Seam for callers: retry_after(key) before verifying credentials, record_failure(key) on a bad
attempt, reset(key) on success. State is per-process only (not shared across replicas).
"""
import threading
import time
from collections import deque
from typing import Callable


class RateLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock  # injectable so tests need no sleeping
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str) -> deque[float]:
        # Caller must hold the lock. Drops failures older than the window.
        attempts = self._failures.get(key)
        if attempts is None:
            return deque()
        cutoff = self._clock() - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
        return attempts

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again; 0 when not blocked."""
        with self._lock:
            attempts = self._prune(key)
            if len(attempts) < self.max_failures:
                return 0
            # Unblocked once the oldest counted failure leaves the window.
            return max(1, int(attempts[0] + self.window_seconds - self._clock() + 0.999))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key)
            self._failures.setdefault(key, deque()).append(self._clock())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        """Drop all state (test isolation)."""
        with self._lock:
            self._failures.clear()


# Shared instance used by the login routes.
login_limiter = RateLimiter()
