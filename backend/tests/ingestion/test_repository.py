from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import cast

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
from ledger_balance.ingestion.repository import (
    BALANCE_SQL,
    CURRENCY_SQL,
    RATE_SQL,
    RESET_SQL,
    STATS_SQL,
    LedgerRepository,
    StoredStats,
)


class FakeConnection:
    def __init__(self, row: Mapping[str, object] | None = None) -> None:
        self.row = row
        self.calls: list[tuple[object, ...]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.calls.append(("execute", query, *args))
        return "OK"

    async def executemany(self, query: str, args: Sequence[Sequence[object]]) -> None:
        self.calls.append(("executemany", query, list(args)))

    async def fetchrow(self, query: str, *args: object) -> Mapping[str, object] | None:
        self.calls.append(("fetchrow", query, *args))
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


def repository_with(connection: FakeConnection) -> tuple[LedgerRepository, FakeDatabase]:
    database = FakeDatabase(connection)
    return LedgerRepository(cast(Database, database)), database


def transaction(*, account_id: int = 100, name: str = "Cash") -> Transaction:
    return Transaction(
        account_id=AccountId(account_id),
        name=name,
        plus=Decimal("0"),
        minus=Decimal("0"),
        currency=CurrencyCode("USD"),
        transaction_date=date(2026, 6, 15),
    )


async def test_reset_uses_one_short_lived_connection_and_exact_sql() -> None:
    connection = FakeConnection()
    repository, database = repository_with(connection)

    await repository.reset()

    assert database.events == ["acquire", "release"]
    assert connection.calls == [("execute", RESET_SQL)]


async def test_insert_rate_book_sorts_currencies_and_rates() -> None:
    eur_rate = Decimal("1.0832")
    gbp_rate = Decimal("1.2710")
    later_eur_rate = Decimal("1.0900")
    rate_book = RateBook.from_rates(
        [
            ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 16), later_eur_rate),
            ExchangeRate(CurrencyCode("GBP"), date(2026, 6, 15), gbp_rate),
            ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), eur_rate),
        ]
    )
    connection = FakeConnection()
    repository, database = repository_with(connection)

    await repository.insert_rate_book(rate_book)

    assert database.events == ["acquire", "release"]
    assert connection.calls == [
        ("executemany", CURRENCY_SQL, [("EUR",), ("GBP",), ("USD",)]),
        (
            "executemany",
            RATE_SQL,
            [
                ("EUR", date(2026, 6, 15), eur_rate),
                ("GBP", date(2026, 6, 15), gbp_rate),
                ("EUR", date(2026, 6, 16), later_eur_rate),
            ],
        ),
    ]
    stored_rates = connection.calls[1][2]
    assert isinstance(stored_rates, list)
    assert stored_rates[0][2] is eur_rate


async def test_eur_only_rate_book_also_inserts_usd_currency_without_usd_rate() -> None:
    rate = Decimal("1.0832")
    rate_book = RateBook.from_rates([ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), rate)])
    connection = FakeConnection()
    repository, _ = repository_with(connection)

    await repository.insert_rate_book(rate_book)

    assert connection.calls == [
        ("executemany", CURRENCY_SQL, [("EUR",), ("USD",)]),
        ("executemany", RATE_SQL, [("EUR", date(2026, 6, 15), rate)]),
    ]


@pytest.mark.parametrize("delta", [Decimal("12.50"), Decimal("-3.75"), Decimal("0")])
async def test_add_balance_delta_uses_positional_arguments_and_preserves_decimal(
    delta: Decimal,
) -> None:
    connection = FakeConnection()
    repository, database = repository_with(connection)
    item = transaction(account_id=243, name="Receivables")

    await repository.add_balance_delta(item, delta)

    assert database.events == ["acquire", "release"]
    assert connection.calls == [("execute", BALANCE_SQL, 243, "Receivables", delta)]
    assert connection.calls[0][4] is delta


async def test_stats_maps_exact_decimal_result() -> None:
    total = Decimal("130.693125")
    connection = FakeConnection({"account_count": 4, "rate_count": 7, "total_usd": total})
    repository, database = repository_with(connection)

    result = await repository.stats()

    assert result == StoredStats(4, 7, total)
    assert result.total_usd is total
    assert database.events == ["acquire", "release"]
    assert connection.calls == [("fetchrow", STATS_SQL)]


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (None, "database statistics query returned no row"),
        (
            {"account_count": "4", "rate_count": 7, "total_usd": Decimal("1")},
            "database statistics returned invalid counts",
        ),
        (
            {"account_count": 4, "rate_count": 7.0, "total_usd": Decimal("1")},
            "database statistics returned invalid counts",
        ),
        (
            {"account_count": 4, "rate_count": 7, "total_usd": "1"},
            "database statistics returned invalid total",
        ),
    ],
)
async def test_stats_rejects_invalid_results(
    row: Mapping[str, object] | None, message: str
) -> None:
    repository, _ = repository_with(FakeConnection(row))

    with pytest.raises(RuntimeError, match=message):
        await repository.stats()


async def test_database_connection_and_fetch_require_connected_pool() -> None:
    database = Database(Settings())

    with pytest.raises(RuntimeError, match="Database pool is not connected"):
        async with database.connection():
            pytest.fail("a disconnected database must not yield a connection")
    with pytest.raises(RuntimeError, match="Database pool is not connected"):
        await database.fetch_value("SELECT $1", True)
