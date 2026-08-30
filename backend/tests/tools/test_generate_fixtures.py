import csv
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from ledger_balance.tools.generate_fixtures import (
    AccountDistribution,
    EntryMode,
    GeneratorConfig,
    RowOrder,
    generate,
)

FILENAMES = (
    "transactions.csv",
    "exchange_rates.csv",
    "expected_balances.csv",
    "expected_summary.csv",
)
CATALOG_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "generated"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def small_config(
    output_dir: Path,
    *,
    rows: int = 120,
    accounts: int = 10,
    dates: int = 4,
    seed: int = 42,
    currencies: tuple[str, ...] = ("USD", "EUR", "GBP"),
    min_amount: Decimal = Decimal("0.01"),
    max_amount: Decimal = Decimal("10000.00"),
    entry_mode: EntryMode = "mixed",
    dual_entry_ratio: Decimal = Decimal("0"),
    zero_delta_ratio: Decimal = Decimal("0"),
    account_distribution: AccountDistribution = "uniform",
    hot_account_ratio: Decimal = Decimal("0.90"),
    pareto_head_count: int = 10,
    pareto_head_ratio: Decimal = Decimal("0.80"),
    order: RowOrder = "interleaved",
    trap_amount_ratio: Decimal = Decimal("0"),
) -> GeneratorConfig:
    return GeneratorConfig(
        output_dir=output_dir,
        rows=rows,
        accounts=accounts,
        dates=dates,
        seed=seed,
        currencies=currencies,
        min_amount=min_amount,
        max_amount=max_amount,
        entry_mode=entry_mode,
        dual_entry_ratio=dual_entry_ratio,
        zero_delta_ratio=zero_delta_ratio,
        account_distribution=account_distribution,
        hot_account_ratio=hot_account_ratio,
        pareto_head_count=pareto_head_count,
        pareto_head_ratio=pareto_head_ratio,
        order=order,
        trap_amount_ratio=trap_amount_ratio,
    )


def independent_balances(output_dir: Path) -> dict[int, Decimal]:
    rates = {
        (row["currency"], row["date"]): Decimal(row["rate"])
        for row in read_rows(output_dir / "exchange_rates.csv")
    }
    balances: dict[int, Decimal] = {}
    with localcontext() as context:
        context.prec = 50
        for row in read_rows(output_dir / "transactions.csv"):
            account_id = int(row["id"])
            delta = (Decimal(row["plus"]) - Decimal(row["minus"])) * rates[
                (row["currency"], row["date"])
            ]
            balances[account_id] = balances.get(account_id, Decimal("0")) + delta
    return balances


def assert_matches_expected_csv(output_dir: Path) -> None:
    calculated = independent_balances(output_dir)
    expected_rows = read_rows(output_dir / "expected_balances.csv")
    expected = {int(row["id"]): Decimal(row["balance_usd"]) for row in expected_rows}
    summary = {row["key"]: row["value"] for row in read_rows(output_dir / "expected_summary.csv")}
    transaction_rows = read_rows(output_dir / "transactions.csv")
    total = sum(calculated.values(), start=Decimal("0"))
    assert expected == calculated
    assert len(expected) == len(expected_rows)
    assert Decimal(summary["total_balance_usd"]) == total
    assert int(summary["transaction_count"]) == len(transaction_rows)
    assert int(summary["account_count"]) == len(expected)
    assert int(summary["account_count"]) == len(calculated)
    if not transaction_rows:
        assert expected == {}
        assert calculated == {}
        assert total == 0


def catalog_directories() -> list[Path]:
    if not CATALOG_ROOT.is_dir():
        return []
    return sorted(
        path
        for path in CATALOG_ROOT.iterdir()
        if path.is_dir() and all((path / name).is_file() for name in FILENAMES)
    )


def catalog_ids() -> list[str]:
    names = [path.name for path in catalog_directories()]
    return names or ["missing"]


def test_generation_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate(small_config(first))
    generate(small_config(second))
    assert_matches_expected_csv(first)
    assert_matches_expected_csv(second)
    for filename in FILENAMES:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_overwrites_the_same_directory(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, seed=1))
    first = {name: (output / name).read_bytes() for name in FILENAMES}
    generate(small_config(output, seed=2))
    second = {name: (output / name).read_bytes() for name in FILENAMES}
    generate(small_config(output, seed=2))
    assert_matches_expected_csv(output)
    for name in FILENAMES:
        assert first[name] != second[name]
        assert (output / name).read_bytes() == second[name]


def test_different_seeds_change_transactions_and_non_usd_rates(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate(small_config(first, seed=1))
    generate(small_config(second, seed=2))
    assert_matches_expected_csv(first)
    assert_matches_expected_csv(second)
    assert (first / "transactions.csv").read_bytes() != (second / "transactions.csv").read_bytes()
    assert (first / "exchange_rates.csv").read_bytes() != (
        second / "exchange_rates.csv"
    ).read_bytes()


def test_expected_balances_and_total_are_exact(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output))
    assert_matches_expected_csv(output)


def test_every_transaction_has_a_rate(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output))
    assert_matches_expected_csv(output)
    rates = {(row["currency"], row["date"]) for row in read_rows(output / "exchange_rates.csv")}
    assert rates == {
        (currency, f"2026-06-{15 + offset:02d}")
        for currency in ("USD", "EUR", "GBP")
        for offset in range(4)
    }
    assert all(
        (row["currency"], row["date"]) in rates for row in read_rows(output / "transactions.csv")
    )


def test_usd_rates_and_fraction_widths(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output))
    assert_matches_expected_csv(output)
    transactions = read_rows(output / "transactions.csv")
    rates = read_rows(output / "exchange_rates.csv")
    assert all(len(row["plus"].partition(".")[2]) == 2 for row in transactions)
    assert all(len(row["minus"].partition(".")[2]) == 2 for row in transactions)
    assert all(len(row["rate"].partition(".")[2]) == 8 for row in rates)
    assert all(row["rate"] == "1.00000000" for row in rates if row["currency"] == "USD")


def test_rows_cover_all_accounts_when_capacity_permits(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, rows=10, accounts=10))
    assert_matches_expected_csv(output)
    assert {row["id"] for row in read_rows(output / "transactions.csv")} == {
        str(account_id) for account_id in range(100, 110)
    }


def test_credit_only_sets_minus_zero(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, entry_mode="credit-only"))
    assert_matches_expected_csv(output)
    assert all(
        Decimal(row["plus"]) > 0 and Decimal(row["minus"]) == 0
        for row in read_rows(output / "transactions.csv")
    )


def test_debit_only_sets_plus_zero(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, entry_mode="debit-only"))
    assert_matches_expected_csv(output)
    assert all(
        Decimal(row["plus"]) == 0 and Decimal(row["minus"]) > 0
        for row in read_rows(output / "transactions.csv")
    )


def test_dual_entry_has_both_sides(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, dual_entry_ratio=Decimal("1")))
    assert_matches_expected_csv(output)
    assert all(
        Decimal(row["plus"]) > 0 and Decimal(row["minus"]) > 0
        for row in read_rows(output / "transactions.csv")
    )


def test_zero_delta_rows_net_to_zero(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, zero_delta_ratio=Decimal("1")))
    assert_matches_expected_csv(output)
    assert all(
        Decimal(row["plus"]) == Decimal(row["minus"])
        for row in read_rows(output / "transactions.csv")
    )


def test_cancel_pairs_have_exact_zero_balances(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, rows=21, entry_mode="cancel-pairs"))
    assert_matches_expected_csv(output)
    calculated = independent_balances(output)
    assert calculated
    assert all(balance == 0 for balance in calculated.values())


def test_hotspot_ratio_one_uses_account_100(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(
        small_config(
            output,
            account_distribution="hotspot",
            hot_account_ratio=Decimal("1"),
        )
    )
    assert_matches_expected_csv(output)
    assert {row["id"] for row in read_rows(output / "transactions.csv")} == {"100"}


def test_pareto_puts_most_rows_on_head_accounts(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(
        small_config(
            output,
            rows=200,
            accounts=50,
            seed=2,
            account_distribution="pareto",
            pareto_head_count=10,
            pareto_head_ratio=Decimal("0.80"),
        )
    )
    assert_matches_expected_csv(output)
    rows = read_rows(output / "transactions.csv")
    head = sum(100 <= int(row["id"]) <= 109 for row in rows)
    assert Decimal(head) / Decimal(len(rows)) >= Decimal("0.80")


def test_by_account_order_is_sorted(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, order="by-account"))
    assert_matches_expected_csv(output)
    ids = [int(row["id"]) for row in read_rows(output / "transactions.csv")]
    assert ids == sorted(ids)


def test_empty_file_has_headers_only(tmp_path: Path) -> None:
    output = tmp_path / "fixture"
    generate(small_config(output, rows=0, accounts=1))
    assert_matches_expected_csv(output)
    assert read_rows(output / "transactions.csv") == []
    summary = {row["key"]: row["value"] for row in read_rows(output / "expected_summary.csv")}
    assert summary["transaction_count"] == "0"
    assert Decimal(summary["total_balance_usd"]) == 0


@pytest.mark.parametrize("catalog_name", catalog_ids())
def test_catalog_dataset_matches_expected_csv(catalog_name: str) -> None:
    catalog_dir = CATALOG_ROOT / catalog_name
    if not all((catalog_dir / name).is_file() for name in FILENAMES):
        pytest.skip(f"catalog directory {catalog_name} is missing")
    assert_matches_expected_csv(catalog_dir)
