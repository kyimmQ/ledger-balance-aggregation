from datetime import date
from decimal import Decimal

import pytest
from ledger_balance.domain.arithmetic import (
    MAX_FRACTIONAL_DIGITS,
    MAX_INTEGER_DIGITS,
    ensure_numeric_38_18,
    transaction_usd_delta,
)
from ledger_balance.domain.models import AccountId, CurrencyCode, Transaction


def make_transaction(*, plus: Decimal, minus: Decimal) -> Transaction:
    return Transaction(
        account_id=AccountId(100),
        name="Cash",
        plus=plus,
        minus=minus,
        currency=CurrencyCode("USD"),
        transaction_date=date(2026, 6, 15),
    )


def test_credit_net_at_unity_rate() -> None:
    transaction = make_transaction(plus=Decimal("250.00"), minus=Decimal("120.50"))

    assert transaction_usd_delta(transaction, Decimal("1")) == Decimal("129.50")


def test_debit_produces_negative_delta() -> None:
    transaction = make_transaction(plus=Decimal("0"), minus=Decimal("50.25"))

    assert transaction_usd_delta(transaction, Decimal("1.5")) == Decimal("-75.375")


def test_equal_sides_yield_exact_zero() -> None:
    transaction = make_transaction(plus=Decimal("10.00"), minus=Decimal("10.00"))

    assert transaction_usd_delta(transaction, Decimal("1.2710")) == Decimal("0.00")


def test_zero_plus_and_minus_yield_exact_zero() -> None:
    transaction = make_transaction(plus=Decimal("0"), minus=Decimal("0"))

    assert transaction_usd_delta(transaction, Decimal("1.0832")) == Decimal("0")


def test_both_sides_positive() -> None:
    transaction = make_transaction(plus=Decimal("100.00"), minus=Decimal("40.00"))

    assert transaction_usd_delta(transaction, Decimal("2")) == Decimal("120.00")


def test_tenth_and_fifth_remain_exact() -> None:
    tenth = make_transaction(plus=Decimal("0.10"), minus=Decimal("0"))
    fifth = make_transaction(plus=Decimal("0.20"), minus=Decimal("0"))
    mixed = make_transaction(plus=Decimal("0.10"), minus=Decimal("0.20"))

    assert transaction_usd_delta(tenth, Decimal("1")) == Decimal("0.10")
    assert transaction_usd_delta(fifth, Decimal("1")) == Decimal("0.20")
    assert transaction_usd_delta(mixed, Decimal("1")) == Decimal("-0.10")


def test_long_fractional_rate_remains_exact() -> None:
    transaction = make_transaction(plus=Decimal("1"), minus=Decimal("0"))
    rate = Decimal("0.123456789012345678")

    assert transaction_usd_delta(transaction, rate) == Decimal("0.123456789012345678")


def test_numeric_38_18_boundaries_pass() -> None:
    integer_boundary = Decimal("9" * MAX_INTEGER_DIGITS)
    fractional_boundary = Decimal(10) ** -MAX_FRACTIONAL_DIGITS
    combined = Decimal("9" * MAX_INTEGER_DIGITS + "." + "9" * MAX_FRACTIONAL_DIGITS)
    twenty_integers = make_transaction(plus=integer_boundary, minus=Decimal("0"))
    eighteen_fractionals = make_transaction(plus=fractional_boundary, minus=Decimal("0"))

    assert ensure_numeric_38_18(integer_boundary, "USD delta") == integer_boundary
    assert ensure_numeric_38_18(-integer_boundary, "USD delta") == -integer_boundary
    assert ensure_numeric_38_18(fractional_boundary, "USD delta") == fractional_boundary
    assert ensure_numeric_38_18(combined, "USD delta") == combined
    assert transaction_usd_delta(twenty_integers, Decimal("1")) == integer_boundary
    assert transaction_usd_delta(eighteen_fractionals, Decimal("1")) == fractional_boundary


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_values_are_rejected(value: Decimal) -> None:
    transaction = make_transaction(plus=Decimal("1"), minus=Decimal("0"))

    with pytest.raises(ValueError, match="USD delta must be finite"):
        ensure_numeric_38_18(value, "USD delta")
    with pytest.raises(ValueError, match="USD delta must be finite"):
        transaction_usd_delta(transaction, value)


def test_21_integer_digits_are_rejected() -> None:
    too_many_integers = Decimal(10) ** MAX_INTEGER_DIGITS
    transaction = make_transaction(plus=too_many_integers, minus=Decimal("0"))

    with pytest.raises(ValueError, match="USD delta does not fit NUMERIC\\(38,18\\)"):
        ensure_numeric_38_18(too_many_integers, "USD delta")
    with pytest.raises(ValueError, match="USD delta does not fit NUMERIC\\(38,18\\)"):
        transaction_usd_delta(transaction, Decimal("1"))


def test_19_fractional_digits_are_rejected() -> None:
    too_many_fractionals = Decimal(10) ** -(MAX_FRACTIONAL_DIGITS + 1)
    transaction = make_transaction(plus=too_many_fractionals, minus=Decimal("0"))

    with pytest.raises(ValueError, match="USD delta does not fit NUMERIC\\(38,18\\)"):
        ensure_numeric_38_18(too_many_fractionals, "USD delta")
    with pytest.raises(ValueError, match="USD delta does not fit NUMERIC\\(38,18\\)"):
        transaction_usd_delta(transaction, Decimal("1"))


def test_out_of_range_product_is_rejected() -> None:
    transaction = make_transaction(plus=Decimal("9" * MAX_INTEGER_DIGITS), minus=Decimal("0"))

    with pytest.raises(ValueError, match="USD delta does not fit NUMERIC\\(38,18\\)"):
        transaction_usd_delta(transaction, Decimal("10"))
