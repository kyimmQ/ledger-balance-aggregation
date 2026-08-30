import os
import warnings
from collections.abc import AsyncGenerator

import asyncpg  # type: ignore[import-untyped]
import pytest
from ledger_balance.config import Settings

LEDGER_TABLES = frozenset({"currencies", "exchange_rates", "account_balances"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.getenv("LEDGER_RUN_DB_TESTS") == "1":
        return

    skip = pytest.mark.skip(reason="set LEDGER_RUN_DB_TESTS=1 to run database tests")
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip)


@pytest.fixture
async def db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    warnings.warn(
        "Integration schema tests truncate all ledger tables in the configured database",
        RuntimeWarning,
        stacklevel=1,
    )
    connection = await asyncpg.connect(Settings().database_url)
    try:
        rows = await connection.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY($1::text[])
            """,
            list(LEDGER_TABLES),
        )
        existing = {row["table_name"] for row in rows}
        missing = LEDGER_TABLES - existing
        if missing:
            pytest.fail(
                "database is not migrated; missing ledger tables: " + ", ".join(sorted(missing))
            )

        await connection.execute("TRUNCATE account_balances, exchange_rates, currencies CASCADE")
        yield connection
    finally:
        if not connection.is_closed():
            await connection.execute(
                "TRUNCATE account_balances, exchange_rates, currencies CASCADE"
            )
            await connection.close()
