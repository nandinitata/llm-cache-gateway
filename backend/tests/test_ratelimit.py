"""Rate limiter, against real Redis."""
from ratelimit import RateLimiter


def test_allows_up_to_the_limit_then_blocks(r):
    rl = RateLimiter(r, limit=3, window_s=60)
    results = [rl.check("clientA")[0] for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_count_is_reported(r):
    rl = RateLimiter(r, limit=5, window_s=60)
    _, count, limit = rl.check("c")
    assert count == 1 and limit == 5


def test_clients_are_independent(r):
    rl = RateLimiter(r, limit=1, window_s=60)
    assert rl.check("alice")[0] is True
    assert rl.check("bob")[0] is True       # different client, own bucket
    assert rl.check("alice")[0] is False    # alice already used her one


def test_short_window_lets_requests_back_in(r):
    import time
    rl = RateLimiter(r, limit=1, window_s=1)
    assert rl.check("c")[0] is True
    assert rl.check("c")[0] is False
    time.sleep(1.1)
    assert rl.check("c")[0] is True         # window slid, allowed again
