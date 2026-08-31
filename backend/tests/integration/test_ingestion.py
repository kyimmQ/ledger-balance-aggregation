import csv
from collections.abc import AsyncGenerator
from decimal import Decimal
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]
import pytest
from ledger_balance.config import Settings
from ledger_balance.db.pool import Database
from ledger_balance.ingestion.service import IngestionResult, ingest
from ledger_balance.input.errors import InputFileError

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPECIFICATION = PROJECT_ROOT / "backend/tests/fixtures/specification"
GENERATED = PROJECT_ROOT / "backend/fixtures/generated"


@pytest.fixture
async def database() -> AsyncGenerator[Database, None]:
    value = Database(Settings())
    await value.connect()
    try:
        yield value
    finally:
        await value.disconnect()


async def ingest_directory(database: Database, directory: Path) -> IngestionResult:
    return await ingest(
        database,
        directory / "transactions.csv",
        directory / "exchange_rates.csv",
    )


async def assert_expected_balances(
    connection: asyncpg.Connection, directory: Path, result: IngestionResult
) -> None:
    with (directory / "expected_balances.csv").open(encoding="utf-8", newline="") as file:
        expected_rows = list(csv.DictReader(file))
    with (directory / "expected_summary.csv").open(encoding="utf-8", newline="") as file:
        summary = {row["key"]: row["value"] for row in csv.DictReader(file)}

    actual_rows = await connection.fetch(
        "SELECT account_id, name, balance_usd FROM account_balances ORDER BY account_id"
    )
    assert [(row["account_id"], row["name"], row["balance_usd"]) for row in actual_rows] == [
        (int(row["id"]), row["name"], Decimal(row["balance_usd"])) for row in expected_rows
    ]
    assert result.transaction_count == int(summary["transaction_count"])
    assert result.account_count == int(summary["account_count"])
    assert result.total_usd == Decimal(summary["total_balance_usd"])


async def test_specification_fixture_persists_exact_balances(
    database: Database, db_connection: asyncpg.Connection
) -> None:
    result = await ingest_directory(database, SPECIFICATION)

    rows = await db_connection.fetch(
        "SELECT account_id, balance_usd FROM account_balances ORDER BY account_id"
    )
    assert [(row["account_id"], row["balance_usd"]) for row in rows] == [
        (100, Decimal("96.407375")),
        (243, Decimal("86.656")),
        (587, Decimal("-58.14825")),
        (912, Decimal("5.778")),
    ]
    assert result == IngestionResult(5, 4, 5, Decimal("130.693125"))


@pytest.mark.parametrize(
    "fixture_name",
    [
        "baseline",
        "cancel-pairs",
        "clustered",
        "credit-only",
        "debit-only",
        "dual-entry",
        "empty",
        "eur-only",
        "float-traps",
        "hotspot",
        "magnitudes",
        "medium-accounts",
        "micro",
        "minimal-accounts",
        "one-per-account",
        "pareto",
        "single-account-fx",
        "single-date",
        "usd-only",
        "zero-delta",
    ],
)
async def test_generated_oracles_match_database_exactly(
    fixture_name: str,
    database: Database,
    db_connection: asyncpg.Connection,
) -> None:
    directory = GENERATED / fixture_name

    result = await ingest_directory(database, directory)

    await assert_expected_balances(db_connection, directory, result)
    if fixture_name == "eur-only":
        currencies = await db_connection.fetch("SELECT code FROM currencies ORDER BY code")
        assert [row["code"] for row in currencies] == ["EUR", "USD"]
        assert (
            await db_connection.fetchval(
                "SELECT count(*) FROM exchange_rates WHERE currency_code = 'USD'"
            )
            == 0
        )
    elif fixture_name == "debit-only":
        assert (
            await db_connection.fetchval(
                "SELECT count(*) FROM account_balances WHERE balance_usd >= 0"
            )
            == 0
        )
    elif fixture_name == "zero-delta":
        assert (
            await db_connection.fetchval(
                "SELECT count(*) FROM account_balances WHERE balance_usd <> 0"
            )
            == 0
        )


async def test_identical_rerun_does_not_double_balances(
    database: Database, db_connection: asyncpg.Connection
) -> None:
    first = await ingest_directory(database, SPECIFICATION)
    first_rows = await db_connection.fetch(
        "SELECT account_id, name, balance_usd FROM account_balances ORDER BY account_id"
    )

    second = await ingest_directory(database, SPECIFICATION)
    second_rows = await db_connection.fetch(
        "SELECT account_id, name, balance_usd FROM account_balances ORDER BY account_id"
    )

    assert second == first
    assert [tuple(row) for row in second_rows] == [tuple(row) for row in first_rows]


async def test_different_dataset_replaces_old_balances_and_rates(
    database: Database, db_connection: asyncpg.Connection
) -> None:
    await ingest_directory(database, SPECIFICATION)

    result = await ingest_directory(database, GENERATED / "micro")

    await assert_expected_balances(db_connection, GENERATED / "micro", result)
    assert await db_connection.fetchval("SELECT count(*) FROM exchange_rates") == result.rate_count


async def test_failure_after_valid_row_leaves_committed_partial_data(
    database: Database, db_connection: asyncpg.Connection, tmp_path: Path
) -> None:
    rates = tmp_path / "exchange_rates.csv"
    rates.write_text("date,currency,rate\n2026-06-15,USD,1\n", encoding="utf-8")
    transactions = tmp_path / "transactions.csv"
    transactions.write_text(
        "id,name,plus,minus,currency,date\n"
        "100,acct100,12.50,0,USD,2026-06-15\n"
        "243,acct243,4.00,0,EUR,2026-06-15\n",
        encoding="utf-8",
    )

    with pytest.raises(InputFileError, match="missing historical rate"):
        await ingest(database, transactions, rates)

    rows = await db_connection.fetch(
        "SELECT account_id, name, balance_usd FROM account_balances ORDER BY account_id"
    )
    assert [tuple(row) for row in rows] == [(100, "acct100", Decimal("12.500000000000000000"))]
