import csv
from decimal import Decimal
from pathlib import Path

from ledger_balance.domain.reference import reduce_transactions
from ledger_balance.input.csv_files import iter_transactions, load_rates
from ledger_balance.tools.generate_fixtures import GeneratorConfig, generate


def test_generated_dataset_matches_expected_csvs(tmp_path: Path) -> None:
    generate(GeneratorConfig(output_dir=tmp_path, rows=50_000))

    rate_book = load_rates(tmp_path / "exchange_rates.csv")
    result = reduce_transactions(
        iter_transactions(tmp_path / "transactions.csv", rate_book),
        rate_book,
    )

    with (tmp_path / "expected_balances.csv").open(encoding="utf-8", newline="") as handle:
        expected_rows = list(csv.DictReader(handle))
    with (tmp_path / "expected_summary.csv").open(encoding="utf-8", newline="") as handle:
        summary = {row["key"]: row["value"] for row in csv.DictReader(handle)}

    assert result.transaction_count == int(summary["transaction_count"]) == 50_000
    assert len(result.balances) == int(summary["account_count"]) == len(expected_rows)
    assert result.total_usd == Decimal(summary["total_balance_usd"])
    for item, row in zip(result.balances, expected_rows, strict=True):
        assert int(item.account_id) == int(row["id"])
        assert item.name == row["name"]
        assert item.balance_usd == Decimal(row["balance_usd"])
