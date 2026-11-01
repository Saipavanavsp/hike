from app.core.redis import get_redis


class FixedWindowLimiter:
    """Counts events per key in a fixed window (Redis INCR + EXPIRE).

    Used for login: only failed attempts are counted, a successful login resets the key.
    """

    def __init__(self, prefix: str, limit: int, window_seconds: int):
        self.prefix = prefix
        self.limit = limit
        self.window = window_seconds

    def _key(self, identity: str) -> str:
        return f"rl:{self.prefix}:{identity}"

    def retry_after(self, identity: str) -> int | None:
        """Seconds until the key unlocks, or None if requests are still allowed."""
        r = get_redis()
        key = self._key(identity)
        count = r.get(key)
        if count is not None and int(count) >= self.limit:
            ttl = r.ttl(key)
            return max(ttl, 1)
        return None

    def hit(self, identity: str) -> int:
        r = get_redis()
        key = self._key(identity)
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window, nx=True)
        count, _ = pipe.execute()
        return int(count)

    def reset(self, identity: str) -> None:
        get_redis().delete(self._key(identity))
