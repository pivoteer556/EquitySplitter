from app.services.rate_limit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(max_failures=3, window=60.0):
    clock = FakeClock()
    return RateLimiter(max_failures, window, clock), clock


def test_blocks_after_max_failures():
    limiter, _ = make()
    for _ in range(2):
        limiter.record_failure("a")
    assert limiter.retry_after("a") == 0
    limiter.record_failure("a")
    assert limiter.retry_after("a") == 60


def test_window_expiry_unblocks():
    limiter, clock = make()
    for _ in range(3):
        limiter.record_failure("a")
    clock.now += 59
    assert limiter.retry_after("a") == 1
    clock.now += 1
    assert limiter.retry_after("a") == 0


def test_reset_clears_failures():
    limiter, _ = make()
    for _ in range(3):
        limiter.record_failure("a")
    limiter.reset("a")
    assert limiter.retry_after("a") == 0


def test_keys_are_independent():
    limiter, _ = make()
    for _ in range(3):
        limiter.record_failure("a")
    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0


def test_clear_drops_all_state():
    limiter, _ = make()
    for _ in range(3):
        limiter.record_failure("a")
    limiter.clear()
    assert limiter.retry_after("a") == 0
