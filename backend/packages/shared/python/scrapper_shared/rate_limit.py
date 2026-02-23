from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=1)
        bucket = self._hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit_per_minute:
            return False
        bucket.append(now)
        return True
