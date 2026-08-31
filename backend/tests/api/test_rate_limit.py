from dataclasses import dataclass

from ledger_balance.api.rate_limit import FixedWindowRateLimiter


@dataclass
class FakeClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value


def test_fixed_window_allows_limit_then_rejects_and_reports_retry() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter(2, 60, 10, clock=clock)

    first = limiter.check("client-a")
    second = limiter.check("client-a")
    third = limiter.check("client-a")

    assert first.allowed and first.remaining == 1
    assert second.allowed and second.remaining == 0
    assert not third.allowed
    assert third.retry_after_seconds == 60


def test_window_resets_after_expiry() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter(1, 10, 10, clock=clock)
    assert limiter.check("client-a").allowed
    assert not limiter.check("client-a").allowed

    clock.value = 10
    decision = limiter.check("client-a")

    assert decision.allowed
    assert decision.remaining == 0


def test_clients_are_isolated_and_forwarded_headers_are_not_an_identity_input() -> None:
    limiter = FixedWindowRateLimiter(1, 60, 10, clock=lambda: 0)

    assert limiter.check("10.0.0.1").allowed
    assert limiter.check("10.0.0.2").allowed
    assert not limiter.check("10.0.0.1").allowed


def test_expired_entries_are_pruned_and_client_memory_is_capped() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter(1, 10, 2, clock=clock)
    limiter.check("client-a")
    limiter.check("client-b")
    assert limiter.client_count == 2

    limiter.check("client-c")
    assert limiter.client_count == 2

    clock.value = 10
    limiter.check("client-d")
    assert limiter.client_count == 1
