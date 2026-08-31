from datetime import date
from decimal import Decimal, getcontext

import pytest
from ledger_balance.api.contracts import (
    AccountBalanceResponse,
    ErrorResponse,
    TotalBalanceResponse,
)
from ledger_balance.api.conversion import convert_usd, format_money
from ledger_balance.api.errors import ApiFinancialError, ValuationRateUnavailableError
from ledger_balance.domain.models import CurrencyCode
from pydantic import ValidationError


def test_usd_conversion_returns_exact_amount_without_rate() -> None:
    amount = Decimal("129.500000000000000000")

    result = convert_usd(amount, CurrencyCode("USD"), None)

    assert result is amount


def test_foreign_conversion_uses_decimal_without_rounding() -> None:
    amount = Decimal("129.500000000000000000")
    rate = Decimal("1.083200000000000000")

    result = convert_usd(amount, CurrencyCode("EUR"), rate)

    assert result == Decimal("119.55317577548005908419497784342688330871491875923")
    exponent = result.as_tuple().exponent
    assert isinstance(exponent, int)
    assert exponent < -2


def test_conversion_does_not_modify_global_context() -> None:
    original = getcontext().prec
    convert_usd(Decimal("10"), CurrencyCode("EUR"), Decimal("1.0832"))
    assert getcontext().prec == original


@pytest.mark.parametrize(
    ("currency", "rate", "exception", "message"),
    [
        ("EUR", None, ValuationRateUnavailableError, "no valuation rate"),
        ("EUR", Decimal("0"), ApiFinancialError, "finite and positive"),
        ("EUR", Decimal("-1"), ApiFinancialError, "finite and positive"),
        ("EUR", Decimal("NaN"), ApiFinancialError, "finite and positive"),
        ("EUR", Decimal("Infinity"), ApiFinancialError, "finite and positive"),
    ],
)
def test_non_usd_conversion_rejects_unusable_rate(
    currency: str,
    rate: Decimal | None,
    exception: type[ApiFinancialError],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        convert_usd(Decimal("10"), CurrencyCode(currency), rate)


def test_non_finite_amount_is_rejected() -> None:
    with pytest.raises(ApiFinancialError, match="finite Decimal"):
        convert_usd(Decimal("NaN"), CurrencyCode("USD"), None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.005"), "1.00"),
        (Decimal("1.015"), "1.02"),
        (Decimal("-1.005"), "-1.00"),
        (Decimal("-1.015"), "-1.02"),
        (Decimal("0"), "0.00"),
        (Decimal("-0.004"), "0.00"),
        (Decimal("12345678901234567890.125"), "12345678901234567890.12"),
    ],
)
def test_format_money_rounds_once_with_half_even(value: Decimal, expected: str) -> None:
    assert format_money(value) == expected


def test_format_money_rejects_non_finite_values() -> None:
    with pytest.raises(ApiFinancialError, match="finite Decimal"):
        format_money(Decimal("Infinity"))


def test_account_response_uses_documented_aliases_and_string_money() -> None:
    response = AccountBalanceResponse(
        accountId=100,
        name="acct100",
        currency="EUR",
        balance="89.00",
        valuationDate=date(2026, 6, 18),
    )

    assert response.model_dump(by_alias=True) == {
        "accountId": 100,
        "name": "acct100",
        "currency": "EUR",
        "balance": "89.00",
        "valuationDate": date(2026, 6, 18),
    }
    assert isinstance(response.balance, str)


def test_total_response_allows_null_usd_valuation_date() -> None:
    response = TotalBalanceResponse(
        currency="USD",
        total="0.00",
        valuationDate=None,
    )

    assert response.model_dump(by_alias=True)["valuationDate"] is None


def test_error_response_uses_request_id_alias() -> None:
    response = ErrorResponse.model_validate(
        {
            "error": {
                "code": "ACCOUNT_NOT_FOUND",
                "message": "Account 999 was not found",
                "requestId": "request-1",
            }
        }
    )

    assert response.model_dump(by_alias=True) == {
        "error": {
            "code": "ACCOUNT_NOT_FOUND",
            "message": "Account 999 was not found",
            "requestId": "request-1",
        }
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"accountId": "100", "name": "acct100", "currency": "USD", "balance": "1.00"},
        {"accountId": 100, "name": "acct100", "currency": "USD", "balance": 1.0},
        {"currency": "USD", "total": "1.00"},
    ],
)
def test_contracts_reject_malformed_required_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        if "accountId" in payload:
            AccountBalanceResponse.model_validate(payload)
        else:
            TotalBalanceResponse.model_validate(payload)
