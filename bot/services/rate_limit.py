from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    scope: str
    max_events: int
    window_seconds: float


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    scope: str
    retry_after_seconds: int = 0


class SlidingWindowRateLimiter:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: dict[tuple[int, str], deque[float]] = {}

    def check(self, *, user_id: int, rule: RateLimitRule) -> RateLimitDecision:
        now = self._clock()
        bucket_key = (user_id, rule.scope)
        bucket = self._events.setdefault(bucket_key, deque())
        self._evict_expired(bucket, now=now, window_seconds=rule.window_seconds)

        if len(bucket) >= rule.max_events:
            retry_after = max(1, int(bucket[0] + rule.window_seconds - now) + 1)
            return RateLimitDecision(
                allowed=False,
                scope=rule.scope,
                retry_after_seconds=retry_after,
            )

        bucket.append(now)
        return RateLimitDecision(allowed=True, scope=rule.scope)

    def check_many(
        self,
        *,
        user_id: int,
        rules: list[RateLimitRule],
    ) -> RateLimitDecision:
        snapshots = {
            rule.scope: deque(self._events.get((user_id, rule.scope), ())) for rule in rules
        }
        for rule in rules:
            decision = self.check(user_id=user_id, rule=rule)
            if not decision.allowed:
                for scope, snapshot in snapshots.items():
                    if snapshot:
                        self._events[(user_id, scope)] = snapshot
                    else:
                        self._events.pop((user_id, scope), None)
                return decision
        return RateLimitDecision(allowed=True, scope="")

    @staticmethod
    def _evict_expired(
        bucket: deque[float],
        *,
        now: float,
        window_seconds: float,
    ) -> None:
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()


rate_limiter = SlidingWindowRateLimiter()
