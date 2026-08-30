from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from ledger_balance.domain.models import (
    AccountId,
    CurrencyCode,
    ExchangeRate,
    RateBook,
    Transaction,
)
from ledger_balance.domain.reference import reduce_transactions
from ledger_balance.input.csv_files import iter_transactions, load_rates

SPECIFICATION_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "specification"


def make_transaction(
    account_id: int,
    name: str,
    plus: str,
    minus: str,
    currency: str = "USD",
    day: int = 15,
) -> Transaction:
    return Transaction(
        account_id=AccountId(account_id),
        name=name,
        plus=Decimal(plus),
        minus=Decimal(minus),
        currency=CurrencyCode(currency),
        transaction_date=date(2026, 6, day),
    )


def usd_rate_book(*days: int) -> RateBook:
    chosen = days or (15,)
    return RateBook.from_rates(
        [
            ExchangeRate(
                currency=CurrencyCode("USD"),
                rate_date=date(2026, 6, day),
                usd_rate=Decimal("1"),
            )
            for day in chosen
        ]
    )


def test_specification_sample_converts_per_row_then_aggregates() -> None:
    rate_book = load_rates(SPECIFICATION_DIR / "exchange_rates.csv")
    result = reduce_transactions(
        iter_transactions(SPECIFICATION_DIR / "transactions.csv", rate_book),
        rate_book,
    )
    expected = {
        100: Decimal("96.407375"),
        243: Decimal("86.656"),
        587: Decimal("-58.14825"),
        912: Decimal("5.778"),
    }
    actual = {int(item.account_id): item.balance_usd for item in result.balances}

    assert actual[100] == Decimal("96.407375")
    assert actual == expected
    assert result.transaction_count == 5
    assert result.total_usd == Decimal("130.693125")
    assert [int(item.account_id) for item in result.balances] == [100, 243, 587, 912]
    assert {int(item.account_id): item.name for item in result.balances} == {
        100: "acct100",
        243: "acct243",
        587: "acct587",
        912: "acct912",
    }


def test_empty_transactions_yield_empty_result() -> None:
    result = reduce_transactions([], RateBook.from_rates([]))

    assert result.balances == ()
    assert result.transaction_count == 0
    assert result.total_usd == Decimal("0")


def test_exact_zero_account_is_retained() -> None:
    result = reduce_transactions(
        [
            make_transaction(200, "acct200", "5.00", "0.00"),
            make_transaction(100, "acct100", "10.00", "10.00"),
        ],
        usd_rate_book(),
    )
    by_id = {int(item.account_id): item for item in result.balances}

    assert result.transaction_count == 2
    assert set(by_id) == {100, 200}
    assert by_id[100].name == "acct100"
    assert by_id[100].balance_usd == Decimal("0.00")
    assert by_id[200].balance_usd == Decimal("5.00")
    assert result.total_usd == Decimal("5.00")


def test_balances_are_ordered_by_account_id() -> None:
    result = reduce_transactions(
        [
            make_transaction(300, "acct300", "3.00", "0.00"),
            make_transaction(100, "acct100", "1.00", "0.00"),
            make_transaction(200, "acct200", "2.00", "0.00"),
            make_transaction(100, "acct100", "4.00", "0.00"),
        ],
        usd_rate_book(),
    )

    assert [int(item.account_id) for item in result.balances] == [100, 200, 300]
    assert [item.balance_usd for item in result.balances] == [
        Decimal("5.00"),
        Decimal("2.00"),
        Decimal("3.00"),
    ]


def test_negative_balances_and_totals_are_kept() -> None:
    result = reduce_transactions(
        [
            make_transaction(100, "acct100", "0.00", "10.00"),
            make_transaction(200, "acct200", "1.00", "6.50"),
        ],
        usd_rate_book(),
    )
    by_id = {int(item.account_id): item.balance_usd for item in result.balances}

    assert by_id[100] == Decimal("-10.00")
    assert by_id[200] == Decimal("-5.50")
    assert result.total_usd == Decimal("-15.50")


def test_accumulated_balance_that_exceeds_numeric_38_18_is_rejected() -> None:
    with pytest.raises(ValueError, match="balance_usd does not fit NUMERIC\\(38,18\\)"):
        reduce_transactions(
            [
                make_transaction(100, "acct100", "9" * 20, "0"),
                make_transaction(100, "acct100", "1", "0"),
            ],
            usd_rate_book(),
        )
