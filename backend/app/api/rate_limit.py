"""A small in-memory sliding-window rate limiter (per client address, per process).

Good enough for one backend instance; a shared store would be needed if the service scales out.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, clock=time.monotonic) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:  # bound memory: drop idle clients
                for idle in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    del self._hits[idle]
            return True
