from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal

import asyncpg  # type: ignore[import-untyped]
import pytest
from ledger_balance.config import Settings
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import (
    AccountId,
    CurrencyCode,
    ExchangeRate,
    RateBook,
    Transaction,
)
from ledger_balance.ingestion.repository import LedgerRepository, StoredStats

pytestmark = pytest.mark.integration


@pytest.fixture
async def repository() -> AsyncGenerator[LedgerRepository, None]:
    database = Database(Settings())
    await database.connect()
    try:
        yield LedgerRepository(database)
    finally:
        await database.disconnect()


def transaction(account_id: int, name: str) -> Transaction:
    return Transaction(
        account_id=AccountId(account_id),
        name=name,
        plus=Decimal("0"),
        minus=Decimal("0"),
        currency=CurrencyCode("USD"),
        transaction_date=date(2026, 6, 15),
    )


async def test_rate_book_reset_and_foreign_key_behavior(
    repository: LedgerRepository, db_connection: asyncpg.Connection
) -> None:
    rate = Decimal("1.083200000000000000")
    await repository.insert_rate_book(
        RateBook.from_rates([ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), rate)])
    )

    currencies = await db_connection.fetch("SELECT code FROM currencies ORDER BY code")
    rates = await db_connection.fetch(
        "SELECT currency_code, rate_date, usd_rate FROM exchange_rates"
    )
    assert [row["code"] for row in currencies] == ["EUR", "USD"]
    assert [tuple(row) for row in rates] == [("EUR", date(2026, 6, 15), rate)]

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await db_connection.execute(
            """
            INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
            VALUES ('GBP', '2026-06-15', 1.271)
            """
        )

    await repository.reset()

    counts = await db_connection.fetchrow(
        """
        SELECT
          (SELECT count(*) FROM currencies) AS currencies,
          (SELECT count(*) FROM exchange_rates) AS rates,
          (SELECT count(*) FROM account_balances) AS balances
        """
    )
    assert counts is not None
    assert tuple(counts) == (0, 0, 0)


async def test_repeated_deltas_stats_and_second_reset(
    repository: LedgerRepository, db_connection: asyncpg.Connection
) -> None:
    await repository.insert_rate_book(
        RateBook.from_rates(
            [
                ExchangeRate(CurrencyCode("USD"), date(2026, 6, 15), Decimal("1")),
                ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), Decimal("1.0832")),
            ]
        )
    )

    await repository.add_balance_delta(transaction(100, "Cash"), Decimal("10.25"))
    await repository.add_balance_delta(transaction(100, "Cash renamed"), Decimal("-3.50"))
    await repository.add_balance_delta(transaction(100, "Cash final"), Decimal("0"))
    await repository.add_balance_delta(transaction(243, "Payable"), Decimal("-8.125"))

    balances = await db_connection.fetch(
        "SELECT account_id, name, balance_usd FROM account_balances ORDER BY account_id"
    )
    assert [tuple(row) for row in balances] == [
        (100, "Cash final", Decimal("6.750000000000000000")),
        (243, "Payable", Decimal("-8.125000000000000000")),
    ]
    assert all(isinstance(row["balance_usd"], Decimal) for row in balances)
    assert await repository.stats() == StoredStats(
        account_count=2,
        rate_count=2,
        total_usd=Decimal("-1.375000000000000000"),
    )

    await repository.reset()

    assert await repository.stats() == StoredStats(0, 0, Decimal("0E-18"))
