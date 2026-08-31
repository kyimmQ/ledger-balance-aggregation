from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Final

from ledger_balance.api.errors import ApiFinancialError, ValuationRateUnavailableError
from ledger_balance.domain.currencies import USD
from ledger_balance.domain.models import CurrencyCode

API_DECIMAL_PRECISION: Final[int] = 50
MONEY_QUANTUM: Final[Decimal] = Decimal("0.01")


def convert_usd(
    amount_usd: Decimal,
    currency: CurrencyCode,
    usd_rate: Decimal | None,
) -> Decimal:
    _require_finite(amount_usd, "USD amount")
    if currency == USD:
        return amount_usd
    if usd_rate is None:
        raise ValuationRateUnavailableError(f"no valuation rate is available for {currency}")
    if not usd_rate.is_finite() or usd_rate <= 0:
        raise ApiFinancialError("valuation rate must be finite and positive")
    with localcontext() as context:
        context.prec = API_DECIMAL_PRECISION
        try:
            converted = amount_usd / usd_rate
        except (InvalidOperation, ZeroDivisionError) as error:
            raise ApiFinancialError("USD conversion failed") from error
    _require_finite(converted, "converted amount")
    return converted


def format_money(amount: Decimal) -> str:
    _require_finite(amount, "money amount")
    with localcontext() as context:
        context.prec = API_DECIMAL_PRECISION
        try:
            rounded = amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
        except InvalidOperation as error:
            raise ApiFinancialError("money amount cannot be represented") from error
    if rounded.is_zero():
        rounded = abs(rounded)
    return format(rounded, ".2f")


def _require_finite(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ApiFinancialError(f"{label} must be a finite Decimal")
