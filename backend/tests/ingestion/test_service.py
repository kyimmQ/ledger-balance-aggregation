from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, cast

import pytest
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import (
    AccountId,
    CurrencyCode,
    ExchangeRate,
    RateBook,
    Transaction,
)
from ledger_balance.ingestion import service
from ledger_balance.ingestion.repository import StoredStats


def transaction(account_id: int, amount: str) -> Transaction:
    return Transaction(
        account_id=AccountId(account_id),
        name=f"acct{account_id}",
        plus=Decimal(amount),
        minus=Decimal("0"),
        currency=CurrencyCode("EUR"),
        transaction_date=date(2026, 6, 15),
    )


class FakeRepository:
    instances: ClassVar[list["FakeRepository"]] = []
    stored_stats = StoredStats(2, 1, Decimal("3.2496"))
    fail_on_write: int | None = None

    def __init__(self, database: Database) -> None:
        self.database = database
        self.events: list[object] = []
        self.write_count = 0
        self.__class__.instances.append(self)

    async def reset(self) -> None:
        self.events.append("reset")

    async def insert_rate_book(self, rate_book: RateBook) -> None:
        self.events.append(("rates", len(rate_book.rates)))

    async def add_balance_delta(self, item: Transaction, delta: Decimal) -> None:
        self.write_count += 1
        self.events.append(("write", int(item.account_id), delta))
        if self.fail_on_write == self.write_count:
            raise RuntimeError("write failed")

    async def stats(self) -> StoredStats:
        self.events.append("stats")
        return self.stored_stats


@pytest.fixture(autouse=True)
def reset_fake_repository() -> None:
    FakeRepository.instances = []
    FakeRepository.stored_stats = StoredStats(2, 1, Decimal("3.2496"))
    FakeRepository.fail_on_write = None


async def test_ingest_validates_rates_then_writes_sequentially_and_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = RateBook.from_rates(
        [ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), Decimal("1.0832"))]
    )
    rows = [transaction(100, "1"), transaction(243, "2")]
    global_events: list[object] = []

    def load_rates(path: Path) -> RateBook:
        global_events.append(("load", path))
        return book

    def iter_transactions(path: Path, rate_book: RateBook):  # type: ignore[no-untyped-def]
        assert rate_book is book
        for index, item in enumerate(rows):
            global_events.append(("yield", index))
            if index:
                assert FakeRepository.instances[0].write_count == index
            yield item

    monkeypatch.setattr(service, "load_rates", load_rates)
    monkeypatch.setattr(service, "iter_transactions", iter_transactions)
    monkeypatch.setattr(service, "LedgerRepository", FakeRepository)

    result = await service.ingest(
        cast(Database, object()), Path("transactions.csv"), Path("rates.csv")
    )

    repository = FakeRepository.instances[0]
    assert global_events == [
        ("load", Path("rates.csv")),
        ("yield", 0),
        ("yield", 1),
    ]
    assert repository.events == [
        "reset",
        ("rates", 1),
        ("write", 100, Decimal("1.0832")),
        ("write", 243, Decimal("2.1664")),
        "stats",
    ]
    assert result == service.IngestionResult(2, 2, 1, Decimal("3.2496"))


async def test_invalid_rate_file_fails_before_repository_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_: Path) -> RateBook:
        raise ValueError("invalid rates")

    monkeypatch.setattr(service, "load_rates", fail)
    monkeypatch.setattr(service, "LedgerRepository", FakeRepository)

    with pytest.raises(ValueError, match="invalid rates"):
        await service.ingest(cast(Database, object()), Path("transactions.csv"), Path("rates.csv"))

    assert FakeRepository.instances == []


async def test_write_failure_stops_iteration_without_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = RateBook.from_rates(
        [ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), Decimal("1.0832"))]
    )
    rows = [transaction(100, "1"), transaction(243, "2"), transaction(587, "3")]
    FakeRepository.fail_on_write = 2
    monkeypatch.setattr(service, "load_rates", lambda _: book)
    monkeypatch.setattr(service, "iter_transactions", lambda _path, _book: iter(rows))
    monkeypatch.setattr(service, "LedgerRepository", FakeRepository)

    with pytest.raises(RuntimeError, match="write failed"):
        await service.ingest(cast(Database, object()), Path("transactions.csv"), Path("rates.csv"))

    assert FakeRepository.instances[0].events == [
        "reset",
        ("rates", 1),
        ("write", 100, Decimal("1.0832")),
        ("write", 243, Decimal("2.1664")),
    ]


async def test_verification_mismatch_reports_expected_and_actual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = RateBook.from_rates(
        [ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), Decimal("1.0832"))]
    )
    FakeRepository.stored_stats = StoredStats(1, 1, Decimal("0"))
    monkeypatch.setattr(service, "load_rates", lambda _: book)
    monkeypatch.setattr(
        service, "iter_transactions", lambda _path, _book: iter([transaction(100, "1")])
    )
    monkeypatch.setattr(service, "LedgerRepository", FakeRepository)

    with pytest.raises(RuntimeError, match="database verification failed: expected"):
        await service.ingest(cast(Database, object()), Path("transactions.csv"), Path("rates.csv"))


async def test_empty_transaction_stream_has_bounded_verification_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = RateBook.from_rates(
        [ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), Decimal("1.0832"))]
    )
    FakeRepository.stored_stats = StoredStats(0, 1, Decimal("0"))
    monkeypatch.setattr(service, "load_rates", lambda _: book)
    monkeypatch.setattr(service, "iter_transactions", lambda _path, _book: iter(()))
    monkeypatch.setattr(service, "LedgerRepository", FakeRepository)

    result = await service.ingest(
        cast(Database, object()), Path("transactions.csv"), Path("rates.csv")
    )

    assert result == service.IngestionResult(0, 0, 1, Decimal("0"))
