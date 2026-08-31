import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from ledger_balance.api.errors import RateLimitExceededError


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int | None


@dataclass(slots=True)
class _Window:
    started_at: float
    count: int


class FixedWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        max_clients: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1 or window_seconds < 1 or max_clients < 1:
            raise ValueError("rate limiter bounds must be positive")
        self._limit = limit
        self._window_seconds = window_seconds
        self._max_clients = max_clients
        self._clock = clock
        self._windows: dict[str, _Window] = {}

    @property
    def client_count(self) -> int:
        return len(self._windows)

    def check(self, client_id: str) -> RateLimitDecision:
        now = self._clock()
        self._prune(now)
        window = self._windows.get(client_id)
        if window is None:
            self._evict_if_full()
            window = _Window(now, 0)
            self._windows[client_id] = window
        elif now - window.started_at >= self._window_seconds:
            window.started_at = now
            window.count = 0

        if window.count >= self._limit:
            retry_after = max(
                1,
                math.ceil(self._window_seconds - (now - window.started_at)),
            )
            return RateLimitDecision(False, self._limit, 0, retry_after)

        window.count += 1
        return RateLimitDecision(True, self._limit, self._limit - window.count, None)

    def _prune(self, now: float) -> None:
        expired = [
            client_id
            for client_id, window in self._windows.items()
            if now - window.started_at >= self._window_seconds
        ]
        for client_id in expired:
            del self._windows[client_id]

    def _evict_if_full(self) -> None:
        if len(self._windows) < self._max_clients:
            return
        oldest_client = next(iter(self._windows))
        del self._windows[oldest_client]


def enforce_rate_limit(request: Request) -> None:
    limiter: FixedWindowRateLimiter = request.app.state.rate_limiter
    client_id = request.client.host if request.client is not None else "unknown"
    decision = limiter.check(client_id)
    request.state.rate_limit_decision = decision
    if not decision.allowed:
        raise RateLimitExceededError(decision.retry_after_seconds or 1)
