from decimal import Decimal
from typing import cast

from fastapi.testclient import TestClient
from ledger_balance.api.app import create_app
from ledger_balance.api.query_models import TotalBalanceSnapshot
from ledger_balance.api.repository import BalanceReadRepository
from ledger_balance.config import Settings


class FakeDatabase:
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def ping(self) -> bool:
        return True


class FakeRepository:
    async def account_snapshot(self, account_id: object, currency: object) -> object:
        del account_id, currency
        raise AssertionError("account endpoint is not used by this test")

    async def total_snapshot(self, currency: object) -> TotalBalanceSnapshot:
        del currency
        return TotalBalanceSnapshot(True, True, Decimal("10"), None, None)


def test_product_requests_are_limited_and_health_is_exempt() -> None:
    settings = Settings(
        api_rate_limit_requests=2,
        api_rate_limit_window_seconds=60,
        api_rate_limit_max_clients=10,
    )
    app = create_app(settings, FakeDatabase(), cast(BalanceReadRepository, FakeRepository()))

    with TestClient(app) as client:
        first = client.get("/api/balances/total")
        second = client.get("/api/balances/total")
        third = client.get("/api/balances/total")
        live = client.get("/health/live")

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert second.status_code == 200
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMITED"
    assert third.headers["X-RateLimit-Limit"] == "2"
    assert third.headers["X-RateLimit-Remaining"] == "0"
    assert third.headers["Retry-After"] == "60"
    assert live.status_code == 200
