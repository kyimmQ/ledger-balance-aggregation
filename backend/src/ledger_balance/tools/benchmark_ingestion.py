import argparse
import asyncio
import platform
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

from ledger_balance.config import Settings, get_settings
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import AccountBalance, AccountId
from ledger_balance.domain.reference import ReferenceResult, reduce_transactions
from ledger_balance.ingestion.service import ingest
from ledger_balance.input.csv_files import iter_transactions, load_rates

BALANCE_ROWS_SQL = """
SELECT account_id, name, balance_usd
FROM account_balances
ORDER BY account_id
"""


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    concurrency: int
    transaction_count: int
    account_count: int
    rate_count: int
    total_usd: Decimal
    elapsed_seconds: float
    rows_per_second: float
    pool_maximum: int
    queue_capacity: int
    maximum_observed_connections: int
    postgresql_version: str


def _validate_concurrencies(values: Sequence[int], pool_maximum: int) -> tuple[int, ...]:
    concurrencies = tuple(values)
    if len(concurrencies) != len(set(concurrencies)):
        raise ValueError("concurrency values must not contain duplicates")
    for concurrency in concurrencies:
        if concurrency < 1:
            raise ValueError("concurrency values must be at least 1")
        if concurrency > pool_maximum:
            raise ValueError(
                f"concurrency {concurrency} exceeds database pool maximum {pool_maximum}"
            )
    return concurrencies


async def _stored_balances(database: Database) -> tuple[AccountBalance, ...]:
    async with database.connection() as connection:
        rows = await connection.fetch(BALANCE_ROWS_SQL)
    return tuple(
        AccountBalance(
            account_id=AccountId(row["account_id"]),
            name=row["name"],
            balance_usd=row["balance_usd"],
        )
        for row in rows
    )


async def benchmark_case(
    settings: Settings,
    transactions_path: Path,
    rates_path: Path,
    concurrency: int,
    reference: ReferenceResult,
) -> BenchmarkResult:
    database = Database(settings)
    await database.connect()
    try:
        started = time.perf_counter()
        ingestion_result = await ingest(
            database,
            transactions_path,
            rates_path,
            concurrency=concurrency,
        )
        elapsed_seconds = time.perf_counter() - started

        actual_balances = await _stored_balances(database)
        if actual_balances != reference.balances:
            raise RuntimeError(
                f"complete account rows differ from sequential oracle at concurrency {concurrency}"
            )
        if ingestion_result.transaction_count != reference.transaction_count:
            raise RuntimeError(
                f"transaction count differs from sequential oracle at concurrency {concurrency}"
            )
        if ingestion_result.total_usd != reference.total_usd:
            raise RuntimeError(
                f"exact total differs from sequential oracle at concurrency {concurrency}"
            )

        postgresql_version = await database.fetch_value("SHOW server_version")
        if not isinstance(postgresql_version, str):
            raise RuntimeError("PostgreSQL returned an invalid server version")
        rows_per_second = (
            ingestion_result.transaction_count / elapsed_seconds
            if elapsed_seconds
            else float("inf")
        )
        return BenchmarkResult(
            concurrency=concurrency,
            transaction_count=ingestion_result.transaction_count,
            account_count=ingestion_result.account_count,
            rate_count=ingestion_result.rate_count,
            total_usd=ingestion_result.total_usd,
            elapsed_seconds=elapsed_seconds,
            rows_per_second=rows_per_second,
            pool_maximum=settings.database_pool_max_size,
            queue_capacity=concurrency,
            maximum_observed_connections=database.maximum_active_connections,
            postgresql_version=postgresql_version,
        )
    finally:
        await database.disconnect()


async def run_benchmarks(
    transactions_path: Path,
    rates_path: Path,
    concurrencies: Sequence[int],
    *,
    settings: Settings | None = None,
) -> tuple[BenchmarkResult, ...]:
    selected_settings = settings or get_settings()
    selected_concurrencies = _validate_concurrencies(
        concurrencies,
        selected_settings.database_pool_max_size,
    )
    rate_book = load_rates(rates_path)
    reference = reduce_transactions(iter_transactions(transactions_path, rate_book), rate_book)
    results = []
    for concurrency in selected_concurrencies:
        results.append(
            await benchmark_case(
                selected_settings,
                transactions_path,
                rates_path,
                concurrency,
                reference,
            )
        )
    return tuple(results)


def print_report(
    transactions_path: Path,
    rates_path: Path,
    results: Sequence[BenchmarkResult],
) -> None:
    postgresql_versions = {result.postgresql_version for result in results}
    postgresql_version = (
        next(iter(postgresql_versions)) if len(postgresql_versions) == 1 else "mixed"
    )
    print(f"Python: {platform.python_version()}")
    print(f"asyncpg: {version('asyncpg')}")
    print(f"PostgreSQL: {postgresql_version}")
    print(f"Platform: {platform.platform()}")
    print(f"Transactions: {transactions_path}")
    print(f"Rates: {rates_path}")
    print()
    print(
        "| Workers | Transactions | Accounts | Rates | Total USD | "
        "Elapsed (s) | Rows/s | Pool max | Queue capacity | Max connections |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        print(
            f"| {result.concurrency} | {result.transaction_count} | "
            f"{result.account_count} | {result.rate_count} | "
            f"{format(result.total_usd, 'f')} | {result.elapsed_seconds:.3f} | "
            f"{result.rows_per_second:.1f} | {result.pool_maximum} | "
            f"{result.queue_capacity} | {result.maximum_observed_connections} |"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark complete concurrent ledger ingestion against its oracle"
    )
    parser.add_argument("--transactions", required=True, type=Path)
    parser.add_argument("--rates", required=True, type=Path)
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 5, 10])
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        results = asyncio.run(
            run_benchmarks(
                arguments.transactions,
                arguments.rates,
                arguments.concurrency,
            )
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print_report(arguments.transactions, arguments.rates, results)


if __name__ == "__main__":
    main()
