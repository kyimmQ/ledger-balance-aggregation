from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from ledger_balance.api.query_models import AccountBalanceSnapshot, TotalBalanceSnapshot
from ledger_balance.api.repository import (
    ACCOUNT_BALANCE_SNAPSHOT_SQL,
    TOTAL_BALANCE_SNAPSHOT_SQL,
    BalanceReadRepository,
)
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import AccountBalance, AccountId, CurrencyCode


class FakeConnection:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self.row = row
        self.calls: list[tuple[object, ...]] = []

    async def fetchrow(
        self, query: str, *args: object, **kwargs: object
    ) -> Mapping[str, object] | None:
        del kwargs
        self.calls.append((query, *args))
        return self.row


class FakeDatabase:
    def __init__(self, connection: FakeConnection) -> None:
        self.fake_connection = connection
        self.events: list[str] = []

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[FakeConnection, None]:
        self.events.append("acquire")
        try:
            yield self.fake_connection
        finally:
            self.events.append("release")


def repository_with(
    row: Mapping[str, object] | None,
) -> tuple[BalanceReadRepository, FakeConnection, FakeDatabase]:
    connection = FakeConnection(row)
    database = FakeDatabase(connection)
    repository = BalanceReadRepository(cast(Database, database))
    return repository, connection, database


async def test_account_snapshot_uses_one_statement_and_preserves_exact_values() -> None:
    rate = Decimal("1.083200000000000000")
    balance = Decimal("129.500000000000000000")
    row = {
        "dataset_ready": True,
        "currency_supported": True,
        "account_id": 100,
        "name": "acct100",
        "balance_usd": balance,
        "usd_rate": rate,
        "valuation_date": date(2026, 6, 18),
    }
    repository, connection, database = repository_with(row)

    result = await repository.account_snapshot(AccountId(100), CurrencyCode("EUR"))

    assert result == AccountBalanceSnapshot(
        dataset_ready=True,
        currency_supported=True,
        account=AccountBalance(AccountId(100), "acct100", balance),
        usd_rate=rate,
        valuation_date=date(2026, 6, 18),
    )
    assert result.account is not None
    assert result.account.balance_usd is balance
    assert result.usd_rate is rate
    assert connection.calls == [(ACCOUNT_BALANCE_SNAPSHOT_SQL, 100, "EUR")]
    assert database.events == ["acquire", "release"]


async def test_account_snapshot_preserves_empty_and_missing_state() -> None:
    row = {
        "dataset_ready": False,
        "currency_supported": False,
        "account_id": None,
        "name": None,
        "balance_usd": None,
        "usd_rate": None,
        "valuation_date": None,
    }
    repository, _, _ = repository_with(row)

    result = await repository.account_snapshot(AccountId(999), CurrencyCode("EUR"))

    assert result == AccountBalanceSnapshot(False, False, None, None, None)


async def test_total_snapshot_uses_one_statement_and_preserves_exact_total() -> None:
    total = Decimal("100.000000000000000000")
    row = {
        "dataset_ready": True,
        "currency_supported": True,
        "total_usd": total,
        "usd_rate": None,
        "valuation_date": None,
    }
    repository, connection, database = repository_with(row)

    result = await repository.total_snapshot(CurrencyCode("USD"))

    assert result == TotalBalanceSnapshot(True, True, total, None, None)
    assert result.total_usd is total
    assert connection.calls == [(TOTAL_BALANCE_SNAPSHOT_SQL, "USD")]
    assert database.events == ["acquire", "release"]


@pytest.mark.parametrize(
    ("row", "method", "message"),
    [
        (None, "total", "balance query returned no row"),
        (
            {
                "dataset_ready": "yes",
                "currency_supported": True,
                "total_usd": Decimal("1"),
                "usd_rate": None,
                "valuation_date": None,
            },
            "total",
            "balance query returned invalid dataset_ready",
        ),
        (
            {
                "dataset_ready": True,
                "currency_supported": True,
                "total_usd": None,
                "usd_rate": None,
                "valuation_date": None,
            },
            "total",
            "total balance query returned inconsistent dataset state",
        ),
        (
            {
                "dataset_ready": True,
                "currency_supported": True,
                "account_id": 100,
                "name": "acct100",
                "balance_usd": "1.00",
                "usd_rate": None,
                "valuation_date": None,
            },
            "account",
            "account balance query returned invalid account data",
        ),
        (
            {
                "dataset_ready": True,
                "currency_supported": True,
                "total_usd": Decimal("1"),
                "usd_rate": Decimal("1"),
                "valuation_date": None,
            },
            "total",
            "balance query returned incomplete valuation data",
        ),
    ],
)
async def test_invalid_query_results_fail_closed(
    row: Mapping[str, object] | None,
    method: str,
    message: str,
) -> None:
    repository, _, _ = repository_with(row)

    with pytest.raises(RuntimeError, match=message):
        if method == "account":
            await repository.account_snapshot(AccountId(100), CurrencyCode("USD"))
        else:
            await repository.total_snapshot(CurrencyCode("USD"))
