import csv
from collections.abc import AsyncGenerator
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient
from ledger_balance.api.app import create_app
from ledger_balance.config import Settings
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import CurrencyCode, RateBook
from ledger_balance.ingestion.service import ingest
from ledger_balance.input.csv_files import load_rates

pytestmark = pytest.mark.integration

# This test truncates every ledger table in the configured DATABASE_URL through
# the shared fixture. Run it only against the dedicated local Docker `ledger`
# database after verifying that target with the documented psql command.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASELINE = PROJECT_ROOT / "backend/fixtures/generated/baseline"


@pytest.fixture
async def ingestion_database() -> AsyncGenerator[Database, None]:
    database = Database(Settings())
    await database.connect()
    try:
        yield database
    finally:
        await database.disconnect()


def _expected_fixture_values() -> tuple[dict[int, Decimal], dict[int, str], dict[str, str]]:
    with (BASELINE / "expected_balances.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (BASELINE / "expected_summary.csv").open(encoding="utf-8", newline="") as handle:
        summary = {row["key"]: row["value"] for row in csv.DictReader(handle)}
    balances = {int(row["id"]): Decimal(row["balance_usd"]) for row in rows}
    names = {int(row["id"]): row["name"] for row in rows}
    return balances, names, summary


def _format_expected_money(amount: Decimal) -> str:
    with localcontext() as context:
        context.prec = 50
        rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    if rounded.is_zero():
        rounded = abs(rounded)
    return format(rounded, ".2f")


def _latest_rate(rates: RateBook, currency: CurrencyCode) -> tuple[Decimal, date]:
    # Keep this calculation independent from the API repository response.
    rate_date, usd_rate = max(
        (
            (rate_date, usd_rate)
            for (code, rate_date), usd_rate in rates.rates.items()
            if code == currency
        ),
        key=lambda item: item[0],
    )
    return usd_rate, rate_date


async def test_baseline_api_reads_are_persisted_restart_safe_and_progressive(
    ingestion_database: Database,
    db_connection: asyncpg.Connection,
) -> None:
    expected_balances, expected_names, expected_summary = _expected_fixture_values()
    rates = load_rates(BASELINE / "exchange_rates.csv")
    expected_total_usd = Decimal(expected_summary["total_balance_usd"])
    expected_account_usd = expected_balances[100]
    expected_account_name = expected_names[100]
    eur_rate, eur_date = _latest_rate(rates, CurrencyCode("EUR"))

    result = await ingest(
        ingestion_database,
        BASELINE / "transactions.csv",
        BASELINE / "exchange_rates.csv",
        concurrency=Settings().ingest_concurrency,
    )
    assert result.transaction_count == int(expected_summary["transaction_count"])
    assert result.account_count == int(expected_summary["account_count"])
    assert result.rate_count == int(expected_summary["rate_count"])
    assert result.total_usd == expected_total_usd
    await ingestion_database.disconnect()

    with TestClient(create_app(Settings(), database=Database(Settings()))) as client:
        account_usd = client.get("/api/accounts/100/balance")
        account_eur = client.get("/api/accounts/100/balance?currency= eur ")
        total_eur = client.get("/api/balances/total?currency=EUR")

        assert account_usd.status_code == 200
        assert account_usd.json() == {
            "accountId": 100,
            "name": expected_account_name,
            "currency": "USD",
            "balance": _format_expected_money(expected_account_usd),
            "valuationDate": None,
        }
        assert account_eur.status_code == 200
        assert account_eur.json() == {
            "accountId": 100,
            "name": expected_account_name,
            "currency": "EUR",
            "balance": _format_expected_money(expected_account_usd / eur_rate),
            "valuationDate": eur_date.isoformat(),
        }
        assert total_eur.status_code == 200
        assert total_eur.json() == {
            "currency": "EUR",
            "total": _format_expected_money(expected_total_usd / eur_rate),
            "valuationDate": eur_date.isoformat(),
        }
    with TestClient(create_app(Settings(), database=Database(Settings()))) as restarted_client:
        restarted_account = restarted_client.get("/api/accounts/100/balance")
        first_total_usd = restarted_client.get("/api/balances/total")

        assert first_total_usd.status_code == 200
        assert first_total_usd.json() == {
            "currency": "USD",
            "total": _format_expected_money(expected_total_usd),
            "valuationDate": None,
        }
        # The baseline occupies every valid account ID. Upsert one additional
        # committed balance delta to demonstrate that a later request observes
        # the live table, while preserving the real ingestion result above.
        await db_connection.execute(
            """
            INSERT INTO account_balances (account_id, name, balance_usd)
            VALUES (100, $1, $2)
            ON CONFLICT (account_id) DO UPDATE
            SET balance_usd = account_balances.balance_usd + EXCLUDED.balance_usd
            """,
            expected_account_name,
            Decimal("1.25"),
        )
        second_total_usd = restarted_client.get("/api/balances/total")

        assert second_total_usd.status_code == 200
        assert second_total_usd.json() == {
            "currency": "USD",
            "total": _format_expected_money(expected_total_usd + Decimal("1.25")),
            "valuationDate": None,
        }

    assert restarted_account.status_code == 200
    assert restarted_account.json()["balance"] == _format_expected_money(expected_account_usd)
