from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path

from ledger_balance.db.pool import Database
from ledger_balance.domain.arithmetic import DECIMAL_PRECISION, transaction_usd_delta
from ledger_balance.domain.models import AccountId
from ledger_balance.ingestion.repository import LedgerRepository, StoredStats
from ledger_balance.input.csv_files import iter_transactions, load_rates


@dataclass(frozen=True, slots=True)
class IngestionResult:
    transaction_count: int
    account_count: int
    rate_count: int
    total_usd: Decimal


async def ingest(database: Database, transactions_path: Path, rates_path: Path) -> IngestionResult:
    rate_book = load_rates(rates_path)
    repository = LedgerRepository(database)

    await repository.reset()
    await repository.insert_rate_book(rate_book)

    transaction_count = 0
    account_ids: set[AccountId] = set()
    expected_total = Decimal("0")
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        for transaction in iter_transactions(transactions_path, rate_book):
            delta = transaction_usd_delta(transaction, rate_book.historical_rate(transaction))
            await repository.add_balance_delta(transaction, delta)
            transaction_count += 1
            account_ids.add(transaction.account_id)
            expected_total += delta

    expected = StoredStats(
        account_count=len(account_ids),
        rate_count=len(rate_book.rates),
        total_usd=expected_total,
    )
    actual = await repository.stats()
    if actual != expected:
        raise RuntimeError(
            "database verification failed: "
            f"expected accounts={expected.account_count}, rates={expected.rate_count}, "
            f"total_usd={expected.total_usd}; "
            f"got accounts={actual.account_count}, rates={actual.rate_count}, "
            f"total_usd={actual.total_usd}"
        )

    return IngestionResult(
        transaction_count=transaction_count,
        account_count=expected.account_count,
        rate_count=expected.rate_count,
        total_usd=expected.total_usd,
    )
