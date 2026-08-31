from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from ledger_balance.api.app import create_app
from ledger_balance.api.query_models import AccountBalanceSnapshot, TotalBalanceSnapshot
from ledger_balance.api.repository import BalanceReadRepository
from ledger_balance.config import Settings
from ledger_balance.domain.models import AccountBalance, AccountId
from pydantic import SecretStr

KEY = "k" * 32


class FakeDatabase:
    def __init__(self) -> None:
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def ping(self) -> bool:
        return self.connected


class CountingRepository:
    def __init__(self) -> None:
        self.account_calls = 0
        self.total_calls = 0

    async def account_snapshot(
        self, account_id: AccountId, currency: object
    ) -> AccountBalanceSnapshot:
        del account_id, currency
        self.account_calls += 1
        return AccountBalanceSnapshot(
            True,
            True,
            AccountBalance(AccountId(100), "acct100", Decimal("10")),
            None,
            None,
        )

    async def total_snapshot(self, currency: object) -> TotalBalanceSnapshot:
        del currency
        self.total_calls += 1
        return TotalBalanceSnapshot(True, True, Decimal("10"), None, None)


def client_with(key: str | None) -> tuple[TestClient, CountingRepository]:
    repository = CountingRepository()
    database = FakeDatabase()
    settings = Settings(api_key=None if key is None else SecretStr(key))
    client = TestClient(create_app(settings, database, cast(BalanceReadRepository, repository)))
    return client, repository


def test_api_key_disabled_allows_product_request() -> None:
    with client_with(None)[0] as client:
        response = client.get("/api/balances/total")

    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-API-Key": "wrong" * 8}],
)
def test_missing_or_invalid_key_returns_same_401_without_repository_access(
    headers: dict[str, str],
) -> None:
    client, repository = client_with(KEY)
    with client:
        response = client.get("/api/balances/total", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.json()["error"]["message"] == "Authentication required"
    assert repository.total_calls == 0


def test_query_string_key_does_not_authenticate() -> None:
    client, repository = client_with(KEY)
    with client:
        response = client.get("/api/balances/total?api_key=" + KEY)

    assert response.status_code == 401
    assert repository.total_calls == 0


def test_valid_key_allows_product_request() -> None:
    with client_with(KEY)[0] as client:
        response = client.get("/api/balances/total", headers={"X-API-Key": KEY})

    assert response.status_code == 200


def test_health_and_openapi_are_public_when_key_is_enabled() -> None:
    with client_with(KEY)[0] as client:
        live = client.get("/health/live")
        schema = client.get("/openapi.json")

    assert live.status_code == 200
    assert schema.status_code == 200
    document = schema.json()
    assert document["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    assert document["paths"]["/api/balances/total"]["get"]["security"] == [{"APIKeyHeader": []}]


def test_cors_allows_api_key_header_for_configured_origin() -> None:
    with client_with(KEY)[0] as client:
        response = client.options(
            "/api/balances/total",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "X-API-Key" in response.headers["access-control-allow-headers"]
