"""In-memory sliding-window rate limiter with exponential backoff for login attempts.

Limits are per container instance (serverless deployments scale horizontally); they are a
brake against brute force and accidental floods, not a global quota.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.config import get_settings
from app.core.errors import TooManyRequests


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._failures: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._failures.clear()

    def check(self, scope: str, key: str, limit: int, window_seconds: int) -> None:
        if not get_settings().ratelimit_enabled:
            return
        now = time.monotonic()
        bucket_key = f"{scope}:{key}"
        with self._lock:
            q = self._hits[bucket_key]
            while q and q[0] < now - window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise TooManyRequests()
            q.append(now)

    def check_backoff(self, scope: str, key: str) -> None:
        """Rejects while an exponential backoff period (after failed logins) is active."""
        if not get_settings().ratelimit_enabled:
            return
        with self._lock:
            entry = self._failures.get(f"{scope}:{key}")
        if entry and entry[1] > time.monotonic():
            raise TooManyRequests()

    def record_failure(self, scope: str, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            count, _ = self._failures.get(f"{scope}:{key}", (0, 0.0))
            count += 1
            delay = min(2 ** max(0, count - 3), 300) if count >= 3 else 0
            self._failures[f"{scope}:{key}"] = (count, now + delay)

    def record_success(self, scope: str, key: str) -> None:
        with self._lock:
            self._failures.pop(f"{scope}:{key}", None)


limiter = RateLimiter()
