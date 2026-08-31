import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
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
from ledger_balance.ingestion.repository import LedgerRepository, StoredStats


def transaction(account_id: int, amount: str) -> Transaction:
    return Transaction(
        account_id=AccountId(account_id),
        name=f"acct{account_id}",
        plus=Decimal(amount),
        minus=Decimal("0"),
        currency=CurrencyCode("EUR"),
        transaction_date=date(2026, 6, 15),
    )


def rate_book() -> RateBook:
    return RateBook.from_rates(
        [ExchangeRate(CurrencyCode("EUR"), date(2026, 6, 15), Decimal("1.0832"))]
    )


class ControlledRepository:
    instances: ClassVar[list["ControlledRepository"]] = []
    instance_created: ClassVar[asyncio.Event]
    stored_stats = StoredStats(2, 1, Decimal("3.2496"))
    call_gates: ClassVar[dict[int, asyncio.Event]] = {}

    def __init__(self, database: Database) -> None:
        self.database = database
        self.events: list[object] = []
        self.calls: list[tuple[Transaction, Decimal]] = []
        self.active_calls = 0
        self.maximum_active_calls = 0
        self.stats_started = asyncio.Event()
        self.started: dict[int, asyncio.Event] = {}
        self.finished: dict[int, asyncio.Event] = {}
        self.completion_order: list[int] = []
        self.__class__.instances.append(self)
        self.__class__.instance_created.set()

    def started_event(self, call_number: int) -> asyncio.Event:
        return self.started.setdefault(call_number, asyncio.Event())

    def finished_event(self, call_number: int) -> asyncio.Event:
        return self.finished.setdefault(call_number, asyncio.Event())

    async def reset(self) -> None:
        self.events.append("reset")

    async def insert_rate_book(self, book: RateBook) -> None:
        self.events.append(("rates", len(book.rates)))

    async def add_balance_delta(self, item: Transaction, delta: Decimal) -> None:
        call_number = len(self.calls) + 1
        self.calls.append((item, delta))
        self.active_calls += 1
        self.maximum_active_calls = max(self.maximum_active_calls, self.active_calls)
        self.events.append(("write_started", call_number, int(item.account_id), delta))
        self.started_event(call_number).set()
        try:
            gate = self.call_gates.get(call_number)
            if gate is not None:
                await gate.wait()
            await asyncio.sleep(0)
            self.completion_order.append(call_number)
            self.events.append(("write_finished", call_number))
            self.finished_event(call_number).set()
        finally:
            self.active_calls -= 1

    async def stats(self) -> StoredStats:
        self.stats_started.set()
        self.events.append("stats")
        return self.stored_stats


@pytest.fixture(autouse=True)
def reset_controlled_repository() -> None:
    ControlledRepository.instances = []
    ControlledRepository.instance_created = asyncio.Event()
    ControlledRepository.stored_stats = StoredStats(2, 1, Decimal("3.2496"))
    ControlledRepository.call_gates = {}


def arrange_ingestion(
    monkeypatch: pytest.MonkeyPatch, rows: list[Transaction], book: RateBook | None = None
) -> RateBook:
    selected_book = book or rate_book()
    monkeypatch.setattr(service, "load_rates", lambda _: selected_book)
    monkeypatch.setattr(service, "iter_transactions", lambda _path, _book: iter(rows))
    monkeypatch.setattr(service, "LedgerRepository", ControlledRepository)
    return selected_book


async def repository_instance() -> ControlledRepository:
    await wait_for(ControlledRepository.instance_created)
    return ControlledRepository.instances[0]


async def wait_for(event: asyncio.Event) -> None:
    await asyncio.wait_for(event.wait(), timeout=1)


async def wait_for_calls_to_start(repository: ControlledRepository, call_numbers: range) -> None:
    for call_number in call_numbers:
        await wait_for(repository.started_event(call_number))


async def test_invalid_concurrency_fails_before_rate_loading_or_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rate_loading_started = False

    def load_rates(_: Path) -> RateBook:
        nonlocal rate_loading_started
        rate_loading_started = True
        return rate_book()

    monkeypatch.setattr(service, "load_rates", load_rates)
    monkeypatch.setattr(service, "LedgerRepository", ControlledRepository)

    with pytest.raises(ValueError, match=r"^ingestion concurrency must be at least 1$"):
        await service.ingest(
            cast(Database, object()),
            Path("transactions.csv"),
            Path("rates.csv"),
            concurrency=0,
        )

    assert not rate_loading_started
    assert ControlledRepository.instances == []


async def test_invalid_rate_file_fails_before_repository_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_: Path) -> RateBook:
        raise ValueError("invalid rates")

    monkeypatch.setattr(service, "load_rates", fail)
    monkeypatch.setattr(service, "LedgerRepository", ControlledRepository)

    with pytest.raises(ValueError, match="invalid rates"):
        await service.ingest(cast(Database, object()), Path("transactions.csv"), Path("rates.csv"))

    assert ControlledRepository.instances == []


async def test_queue_capacity_and_maximum_active_calls_equal_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [transaction(100 + index, str(index + 1)) for index in range(6)]
    arrange_ingestion(monkeypatch, rows)
    ControlledRepository.call_gates = {call_number: asyncio.Event() for call_number in range(1, 4)}
    queue_sizes: list[int] = []
    real_queue = asyncio.Queue

    def capturing_queue(*, maxsize: int = 0) -> asyncio.Queue[service.QueueItem]:
        queue_sizes.append(maxsize)
        return real_queue(maxsize=maxsize)

    monkeypatch.setattr(
        service,
        "asyncio",
        SimpleNamespace(Queue=capturing_queue, TaskGroup=asyncio.TaskGroup),
    )

    ingestion = asyncio.create_task(
        service.ingest(
            cast(Database, object()),
            Path("transactions.csv"),
            Path("rates.csv"),
            concurrency=3,
        )
    )
    repository = await repository_instance()
    await wait_for_calls_to_start(repository, range(1, 4))

    assert queue_sizes == [3]
    assert repository.active_calls == 3
    assert repository.maximum_active_calls == 3

    for gate in ControlledRepository.call_gates.values():
        gate.set()
    result = await ingestion

    assert len(repository.calls) == 6
    assert repository.maximum_active_calls == 3
    assert result.transaction_count == 6


async def test_each_produced_row_is_written_once_even_when_rows_are_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = transaction(100, "1")
    rows = [duplicate, duplicate, transaction(243, "2")]
    arrange_ingestion(monkeypatch, rows)

    result = await service.ingest(
        cast(Database, object()),
        Path("transactions.csv"),
        Path("rates.csv"),
        concurrency=2,
    )

    repository = ControlledRepository.instances[0]
    assert [item for item, _delta in repository.calls] == rows
    assert repository.calls.count((duplicate, Decimal("1.0832"))) == 2
    assert result.transaction_count == 3


async def test_completion_order_may_differ_from_input_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [transaction(100, "1"), transaction(243, "2"), transaction(587, "3")]
    arrange_ingestion(monkeypatch, rows)
    ControlledRepository.call_gates = {call_number: asyncio.Event() for call_number in range(1, 4)}

    ingestion = asyncio.create_task(
        service.ingest(
            cast(Database, object()),
            Path("transactions.csv"),
            Path("rates.csv"),
            concurrency=3,
        )
    )
    repository = await repository_instance()
    await wait_for_calls_to_start(repository, range(1, 4))

    for call_number in (2, 1, 3):
        ControlledRepository.call_gates[call_number].set()
        await wait_for(repository.finished_event(call_number))

    result = await ingestion

    assert repository.completion_order == [2, 1, 3]
    assert result == service.IngestionResult(3, 2, 1, Decimal("3.2496"))


async def test_stats_and_success_wait_for_slowest_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [transaction(100, "1"), transaction(243, "2"), transaction(587, "3")]
    arrange_ingestion(monkeypatch, rows)
    ControlledRepository.call_gates = {1: asyncio.Event()}

    ingestion = asyncio.create_task(
        service.ingest(
            cast(Database, object()),
            Path("transactions.csv"),
            Path("rates.csv"),
            concurrency=3,
        )
    )
    repository = await repository_instance()
    await wait_for(repository.started_event(1))
    await wait_for(repository.finished_event(2))
    await wait_for(repository.finished_event(3))

    assert not ingestion.done()
    assert not repository.stats_started.is_set()

    ControlledRepository.call_gates[1].set()
    await ingestion

    assert repository.events[-1] == "stats"
    assert repository.stats_started.is_set()


async def test_result_uses_actual_database_stats_without_runtime_expected_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [transaction(100, "1"), transaction(243, "2")]
    arrange_ingestion(monkeypatch, rows)
    ControlledRepository.stored_stats = StoredStats(91, 37, Decimal("-987654.321098"))

    result = await service.ingest(
        cast(Database, object()), Path("transactions.csv"), Path("rates.csv")
    )

    assert result == service.IngestionResult(2, 91, 37, Decimal("-987654.321098"))


async def test_empty_transaction_stream_stops_all_workers_and_reports_actual_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arrange_ingestion(monkeypatch, [])
    ControlledRepository.stored_stats = StoredStats(0, 1, Decimal("0"))
    worker_count = 0
    consume = service._consume

    async def counting_consume(
        queue: asyncio.Queue[service.QueueItem], repository: ControlledRepository
    ) -> None:
        nonlocal worker_count
        worker_count += 1
        await consume(queue, cast(LedgerRepository, repository))

    monkeypatch.setattr(service, "_consume", counting_consume)

    result = await service.ingest(
        cast(Database, object()),
        Path("transactions.csv"),
        Path("rates.csv"),
        concurrency=3,
    )

    repository = ControlledRepository.instances[0]
    assert worker_count == 3
    assert repository.calls == []
    assert repository.events == ["reset", ("rates", 1), "stats"]
    assert result == service.IngestionResult(0, 0, 1, Decimal("0"))
