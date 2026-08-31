from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from ledger_balance.api.app import create_app
from ledger_balance.api.query_models import AccountBalanceSnapshot, TotalBalanceSnapshot
from ledger_balance.api.repository import BalanceReadRepository
from ledger_balance.config import Settings
from ledger_balance.domain.models import AccountBalance, AccountId, CurrencyCode


class FakeDatabase:
    def __init__(self) -> None:
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def ping(self) -> bool:
        return self.connected


class FakeRepository:
    def __init__(self) -> None:
        self.account_result = AccountBalanceSnapshot(
            True,
            True,
            AccountBalance(AccountId(100), "acct100", Decimal("129.500000000000000000")),
            Decimal("1.100000000000000000"),
            date(2026, 6, 17),
        )
        self.total_result = TotalBalanceSnapshot(
            True,
            True,
            Decimal("100.000000000000000000"),
            Decimal("1.100000000000000000"),
            date(2026, 6, 17),
        )
        self.account_error: Exception | None = None
        self.total_error: Exception | None = None

    async def account_snapshot(
        self, account_id: AccountId, currency: CurrencyCode
    ) -> AccountBalanceSnapshot:
        del account_id, currency
        if self.account_error is not None:
            raise self.account_error
        return self.account_result

    async def total_snapshot(self, currency: CurrencyCode) -> TotalBalanceSnapshot:
        del currency
        if self.total_error is not None:
            raise self.total_error
        return self.total_result


def client_with(
    repository: FakeRepository,
) -> tuple[TestClient, FakeDatabase]:
    database = FakeDatabase()
    client = TestClient(
        create_app(
            Settings(api_allowed_origins="http://localhost:5173"),
            database,
            cast(BalanceReadRepository, repository),
        ),
        raise_server_exceptions=False,
    )
    return client, database


def test_account_and_total_use_shared_conversion_contract() -> None:
    repository = FakeRepository()
    with client_with(repository)[0] as client:
        account = client.get("/api/accounts/100/balance?currency= eur ")
        total = client.get("/api/balances/total?currency=EUR")

    assert account.status_code == 200
    assert account.json() == {
        "accountId": 100,
        "name": "acct100",
        "currency": "EUR",
        "balance": "117.73",
        "valuationDate": "2026-06-17",
    }
    assert total.status_code == 200
    assert total.json() == {
        "currency": "EUR",
        "total": "90.91",
        "valuationDate": "2026-06-17",
    }


def test_omitted_currency_defaults_to_usd_and_request_id_is_echoed() -> None:
    with client_with(FakeRepository())[0] as client:
        response = client.get(
            "/api/accounts/100/balance",
            headers={"X-Request-ID": "client-request-1"},
        )

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"
    assert response.json()["balance"] == "129.50"
    assert response.json()["valuationDate"] is None
    assert response.headers["X-Request-ID"] == "client-request-1"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/api/accounts/99/balance", "INVALID_ACCOUNT_ID"),
        ("/api/accounts/nope/balance", "INVALID_ACCOUNT_ID"),
        ("/api/balances/total?currency=US$", "INVALID_CURRENCY"),
    ],
)
def test_invalid_inputs_use_structured_400(path: str, code: str) -> None:
    with client_with(FakeRepository())[0] as client:
        response = client.get(path)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_missing_account_and_unsupported_currency_are_distinct() -> None:
    repository = FakeRepository()
    repository.account_result = AccountBalanceSnapshot(True, True, None, None, None)
    with client_with(repository)[0] as client:
        missing = client.get("/api/accounts/999/balance")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"

    repository.total_result = TotalBalanceSnapshot(
        True, False, Decimal("100.000000000000000000"), None, None
    )
    with client_with(repository)[0] as client:
        unsupported = client.get("/api/balances/total?currency=EUR")
    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_CURRENCY"


def test_empty_dataset_and_missing_rate_are_explicit_failures() -> None:
    repository = FakeRepository()
    repository.total_result = TotalBalanceSnapshot(False, False, None, None, None)
    with client_with(repository)[0] as client:
        empty = client.get("/api/balances/total")
    assert empty.status_code == 503
    assert empty.json()["error"]["code"] == "DATASET_NOT_READY"

    repository.total_result = TotalBalanceSnapshot(True, True, Decimal("100"), None, None)
    with client_with(repository)[0] as client:
        missing_rate = client.get("/api/balances/total?currency=EUR")
    assert missing_rate.status_code == 503
    assert missing_rate.json()["error"]["code"] == "VALUATION_RATE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (OSError("connection refused"), 503, "DATABASE_UNAVAILABLE"),
        (TimeoutError("query timed out"), 504, "DATABASE_TIMEOUT"),
        (RuntimeError("secret SQL details"), 500, "INTERNAL_ERROR"),
    ],
)
def test_repository_failures_are_safe(error: Exception, status_code: int, code: str) -> None:
    repository = FakeRepository()
    repository.total_error = error
    with client_with(repository)[0] as client:
        response = client.get("/api/balances/total")

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert "secret SQL details" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_framework_404_and_405_use_the_common_envelope() -> None:
    with client_with(FakeRepository())[0] as client:
        not_found = client.get("/missing")
        method = client.post("/api/balances/total")

    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "NOT_FOUND"
    assert method.status_code == 405
    assert method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
