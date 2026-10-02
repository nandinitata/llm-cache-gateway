"""A sliding-window rate limiter, done atomically in Redis with one Lua script.

Each client gets a sorted set of request timestamps. The script drops anything
older than the window, counts what's left, and only adds the new request if the
client is under the limit. One round trip, no races.
"""
from __future__ import annotations

import os
import time
import uuid

import redis

# drop old entries, count, add-if-under-limit. Returns {allowed, count}.
_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  return {0, count}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return {1, count + 1}
"""

DEFAULT_LIMIT = int(os.environ.get("RATE_LIMIT", "20"))
DEFAULT_WINDOW_S = int(os.environ.get("RATE_WINDOW_S", "60"))


class RateLimiter:
    def __init__(self, r: redis.Redis, limit: int = DEFAULT_LIMIT, window_s: int = DEFAULT_WINDOW_S):
        self.r = r
        self.limit = limit
        self.window_ms = window_s * 1000
        self._script = r.register_script(_LUA)

    def check(self, client_id: str) -> tuple[bool, int, int]:
        """Returns (allowed, current_count, limit)."""
        now = int(time.time() * 1000)
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        allowed, count = self._script(
            keys=[f"rl:{client_id}"],
            args=[now, self.window_ms, self.limit, member],
        )
        return bool(allowed), int(count), self.limit
