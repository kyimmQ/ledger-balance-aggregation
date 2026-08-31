import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]

from ledger_balance.config import get_settings
from ledger_balance.db.pool import Database
from ledger_balance.ingestion.service import IngestionResult, ingest
from ledger_balance.input.errors import InputFileError


async def run(transactions_path: Path, rates_path: Path) -> IngestionResult:
    database = Database(get_settings())
    await database.connect()
    try:
        return await ingest(database, transactions_path, rates_path)
    finally:
        await database.disconnect()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest ledger CSV files into PostgreSQL")
    parser.add_argument("--transactions", required=True, type=Path)
    parser.add_argument("--rates", required=True, type=Path)
    arguments = parser.parse_args(argv)

    try:
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

    print(
        f"ingested transactions={result.transaction_count} "
        f"accounts={result.account_count} rates={result.rate_count} "
        f"total_usd={format(result.total_usd, 'f')}"
    )


if __name__ == "__main__":
    main()
