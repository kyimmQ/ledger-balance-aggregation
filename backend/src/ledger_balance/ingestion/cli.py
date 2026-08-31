import argparse
import asyncio
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]

from ledger_balance.config import get_settings
from ledger_balance.db.pool import Database
from ledger_balance.ingestion.models import IngestionResult
from ledger_balance.ingestion.service import ingest
from ledger_balance.input.errors import InputFileError


async def run(transactions_path: Path, rates_path: Path) -> IngestionResult:
    settings = get_settings()
    database = Database(settings)
    await database.connect()
    try:
        return await ingest(
            database,
            transactions_path,
            rates_path,
            concurrency=settings.ingest_concurrency,
        )
    finally:
        await database.disconnect()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest ledger CSV files into PostgreSQL")
    parser.add_argument("--transactions", required=True, type=Path)
    parser.add_argument("--rates", required=True, type=Path)
    arguments = parser.parse_args(argv)

    try:
        started = time.perf_counter()
        result = asyncio.run(run(arguments.transactions, arguments.rates))
    except (
        InputFileError,
        OSError,
        asyncpg.PostgresError,
        asyncpg.InterfaceError,
        RuntimeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    elapsed_seconds = max(time.perf_counter() - started, 1e-9)
    rows_per_second = result.transaction_count / elapsed_seconds
    print(
        f"ingested transactions={result.transaction_count} "
        f"accounts={result.account_count} rates={result.rate_count} "
        f"total_usd={format(result.total_usd, 'f')} "
        f"elapsed_seconds={elapsed_seconds:.6f} "
        f"rows_per_second={rows_per_second:.6f}"
    )


if __name__ == "__main__":
    main()
