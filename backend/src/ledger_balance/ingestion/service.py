import asyncio
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ledger_balance.db.pool import Database
from ledger_balance.domain.arithmetic import transaction_usd_delta
from ledger_balance.domain.models import RateBook, Transaction
from ledger_balance.ingestion.errors import WorkItemPersistenceError
from ledger_balance.ingestion.models import IngestionResult
from ledger_balance.ingestion.repository import LedgerRepository
from ledger_balance.input.csv_files import iter_transactions, load_rates


@dataclass(frozen=True, slots=True)
class BalanceWorkItem:
    sequence: int
    transaction: Transaction
    delta: Decimal


@dataclass(frozen=True, slots=True)
class _StopSignal:
    pass


_STOP = _StopSignal()
type QueueItem = BalanceWorkItem | _StopSignal


async def _produce(
    queue: asyncio.Queue[QueueItem],
    transactions_path: Path,
    rate_book: RateBook,
    worker_count: int,
) -> int:
    transaction_count = 0
    for sequence, transaction in enumerate(
        iter_transactions(transactions_path, rate_book), start=1
    ):
        delta = transaction_usd_delta(transaction, rate_book.historical_rate(transaction))
        await queue.put(BalanceWorkItem(sequence, transaction, delta))
        transaction_count = sequence

    for _ in range(worker_count):
        await queue.put(_STOP)
    return transaction_count


async def _consume(queue: asyncio.Queue[QueueItem], repository: LedgerRepository) -> None:
    while True:
        item = await queue.get()
        if isinstance(item, _StopSignal):
            return
        try:
            await repository.add_balance_delta(item.transaction, item.delta)
        except Exception as error:
            raise WorkItemPersistenceError(item.sequence, error) from error


def _first_exception(error: ExceptionGroup[Exception]) -> Exception:
    for exception in error.exceptions:
        if isinstance(exception, ExceptionGroup):
            return _first_exception(exception)
        return exception
    raise RuntimeError("task group failed without an exception")


async def _run_pipeline(
    repository: LedgerRepository,
    transactions_path: Path,
    rate_book: RateBook,
    concurrency: int,
) -> int:
    queue: asyncio.Queue[QueueItem] = asyncio.Queue(maxsize=concurrency)
    try:
        async with asyncio.TaskGroup() as tasks:
            producer = tasks.create_task(_produce(queue, transactions_path, rate_book, concurrency))
            for _ in range(concurrency):
                tasks.create_task(_consume(queue, repository))
    except ExceptionGroup as error:
        raise _first_exception(error) from None
    return producer.result()


async def ingest(
    database: Database,
    transactions_path: Path,
    rates_path: Path,
    *,
    concurrency: int = 1,
) -> IngestionResult:
    if concurrency < 1:
        raise ValueError("ingestion concurrency must be at least 1")

    rate_book = load_rates(rates_path)
    repository = LedgerRepository(database)
    await repository.reset()
    await repository.insert_rate_book(rate_book)

    transaction_count = await _run_pipeline(repository, transactions_path, rate_book, concurrency)
    actual = await repository.stats()
    return IngestionResult(
        transaction_count=transaction_count,
        account_count=actual.account_count,
        rate_count=actual.rate_count,
        total_usd=actual.total_usd,
    )
