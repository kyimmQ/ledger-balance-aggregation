from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal

import asyncpg  # type: ignore[import-untyped]
import pytest
from ledger_balance.api.query_models import AccountBalanceSnapshot, TotalBalanceSnapshot
from ledger_balance.api.repository import BalanceReadRepository
from ledger_balance.config import Settings
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import AccountBalance, AccountId, CurrencyCode

pytestmark = pytest.mark.integration


@pytest.fixture
async def repository() -> AsyncGenerator[BalanceReadRepository, None]:
    database = Database(Settings())
    await database.connect()
    try:
        yield BalanceReadRepository(database)
    finally:
        await database.disconnect()


async def insert_currencies(connection: asyncpg.Connection, *codes: str) -> None:
    await connection.executemany(
        "INSERT INTO currencies (code) VALUES ($1)",
        [(code,) for code in codes],
    )


async def insert_account(
    connection: asyncpg.Connection,
    account_id: int,
    name: str,
    balance: str,
) -> None:
    await connection.execute(
        """
        INSERT INTO account_balances (account_id, name, balance_usd)
        VALUES ($1, $2, $3)
        """,
        account_id,
        name,
        Decimal(balance),
    )


async def test_empty_dataset_returns_one_typed_state(
    repository: BalanceReadRepository,
    db_connection: asyncpg.Connection,
) -> None:
    del db_connection

    account = await repository.account_snapshot(AccountId(100), CurrencyCode("USD"))
    total = await repository.total_snapshot(CurrencyCode("USD"))

    assert account == AccountBalanceSnapshot(False, False, None, None, None)
    assert total == TotalBalanceSnapshot(False, False, None, None, None)


async def test_account_and_total_preserve_exact_values_and_latest_requested_rate(
    repository: BalanceReadRepository,
    db_connection: asyncpg.Connection,
) -> None:
    await insert_currencies(db_connection, "USD", "EUR", "GBP")
    await db_connection.executemany(
        """
        INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
        VALUES ($1, $2, $3)
        """,
        [
            ("EUR", date(2026, 6, 15), Decimal("1.0832")),
            ("EUR", date(2026, 6, 17), Decimal("1.1000")),
            ("GBP", date(2026, 6, 18), Decimal("1.2710")),
            ("USD", date(2026, 6, 18), Decimal("1")),
        ],
    )
    await insert_account(db_connection, 100, "acct100", "129.50")
    await insert_account(db_connection, 243, "acct243", "-29.50")

    account = await repository.account_snapshot(AccountId(100), CurrencyCode("EUR"))
    total = await repository.total_snapshot(CurrencyCode("EUR"))
    usd = await repository.account_snapshot(AccountId(100), CurrencyCode("USD"))

    assert account == AccountBalanceSnapshot(
        True,
        True,
        AccountBalance(AccountId(100), "acct100", Decimal("129.500000000000000000")),
        Decimal("1.100000000000000000"),
        date(2026, 6, 17),
    )
    assert total == TotalBalanceSnapshot(
        True,
        True,
        Decimal("100.000000000000000000"),
        Decimal("1.100000000000000000"),
        date(2026, 6, 17),
    )
    assert usd.usd_rate is None
    assert usd.valuation_date is None


async def test_populated_dataset_distinguishes_missing_account_and_unsupported_currency(
    repository: BalanceReadRepository,
    db_connection: asyncpg.Connection,
) -> None:
    await insert_currencies(db_connection, "USD")
    await insert_account(db_connection, 100, "acct100", "0")

    missing = await repository.account_snapshot(AccountId(999), CurrencyCode("USD"))
    unsupported = await repository.total_snapshot(CurrencyCode("EUR"))

    assert missing == AccountBalanceSnapshot(True, True, None, None, None)
    assert unsupported == TotalBalanceSnapshot(
        True,
        False,
        Decimal("0E-18"),
        None,
        None,
    )


async def test_supported_non_usd_currency_without_rate_is_preserved_as_state(
    repository: BalanceReadRepository,
    db_connection: asyncpg.Connection,
) -> None:
    await insert_currencies(db_connection, "USD", "EUR")
    await insert_account(db_connection, 100, "acct100", "10")

    result = await repository.total_snapshot(CurrencyCode("EUR"))

    assert result == TotalBalanceSnapshot(
        True,
        True,
        Decimal("10.000000000000000000"),
        None,
        None,
    )


async def test_separate_reads_observe_progressively_committed_balances(
    repository: BalanceReadRepository,
    db_connection: asyncpg.Connection,
) -> None:
    await insert_currencies(db_connection, "USD")
    await insert_account(db_connection, 100, "acct100", "10")

    first = await repository.total_snapshot(CurrencyCode("USD"))
    await insert_account(db_connection, 243, "acct243", "-3")
    second = await repository.total_snapshot(CurrencyCode("USD"))

    assert first.total_usd == Decimal("10.000000000000000000")
    assert second.total_usd == Decimal("7.000000000000000000")
