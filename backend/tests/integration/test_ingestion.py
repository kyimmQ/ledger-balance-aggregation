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
DEFAULT_CONCURRENCY = 10


@pytest.fixture
async def database() -> AsyncGenerator[Database, None]:
    value = Database(Settings())
    await value.connect()
    try:
        yield value
    finally:
        await value.disconnect()


async def ingest_directory(
    database: Database,
    directory: Path,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> IngestionResult:
    return await ingest(
        database,
        directory / "transactions.csv",
        directory / "exchange_rates.csv",
        concurrency=concurrency,
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


@pytest.mark.parametrize("attempt", range(3))
async def test_hot_account_repeated_runs_lose_no_updates(
    attempt: int,
    database: Database,
    db_connection: asyncpg.Connection,
) -> None:
    del attempt
    directory = GENERATED / "hotspot"

    result = await ingest_directory(database, directory, concurrency=10)

    await assert_expected_balances(db_connection, directory, result)
    rows = await db_connection.fetch(
        "SELECT account_id, balance_usd FROM account_balances ORDER BY account_id"
    )
    assert [tuple(row) for row in rows] == [(100, Decimal("788150.493642082600000000"))]


@pytest.mark.parametrize(
    ("fixture_name", "concurrency"),
    [
        ("minimal-accounts", 2),
        ("minimal-accounts", 5),
        ("minimal-accounts", 10),
        ("baseline", 10),
        ("pareto", 10),
    ],
)
async def test_contention_distributions_match_oracle(
    fixture_name: str,
    concurrency: int,
    database: Database,
    db_connection: asyncpg.Connection,
) -> None:
    directory = GENERATED / fixture_name

    result = await ingest_directory(database, directory, concurrency=concurrency)

    await assert_expected_balances(db_connection, directory, result)


async def test_failure_leaves_only_exact_valid_prefix_and_clean_rerun_recovers(
    database: Database, db_connection: asyncpg.Connection, tmp_path: Path
) -> None:
    rates = tmp_path / "exchange_rates.csv"
    rates.write_text("date,currency,rate\n2026-06-15,USD,1\n", encoding="utf-8")
    transactions = tmp_path / "transactions.csv"
    valid_prefix = {
        account_id: (f"acct{account_id}", Decimal(f"{account_id - 99}.25"))
        for account_id in range(100, 125)
    }
    rows = ["id,name,plus,minus,currency,date"]
    rows.extend(
        f"{account_id},{name},{amount},0,USD,2026-06-15"
        for account_id, (name, amount) in valid_prefix.items()
    )
    rows.append("999,invalid,4.00,0,EUR,2026-06-15")
    transactions.write_text("\n".join(rows) + "\n", encoding="utf-8")

    result: IngestionResult | None = None
    with pytest.raises(InputFileError, match="missing historical rate"):
        result = await ingest(
            database,
            transactions,
            rates,
            concurrency=DEFAULT_CONCURRENCY,
        )
    assert result is None

    stored_rows = await db_connection.fetch(
        "SELECT account_id, name, balance_usd FROM account_balances ORDER BY account_id"
    )
    stored_ids = [row["account_id"] for row in stored_rows]
    assert len(stored_ids) == len(set(stored_ids))
    assert set(stored_ids) <= set(valid_prefix)
    assert 999 not in stored_ids
    for row in stored_rows:
        expected_name, expected_balance = valid_prefix[row["account_id"]]
        assert (row["name"], row["balance_usd"]) == (expected_name, expected_balance)

    recovery_directory = GENERATED / "micro"
    recovery_result = await ingest_directory(database, recovery_directory)
    await assert_expected_balances(db_connection, recovery_directory, recovery_result)
