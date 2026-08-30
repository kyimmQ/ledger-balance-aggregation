from decimal import Decimal, localcontext
from typing import Final

from ledger_balance.domain.models import Transaction

DECIMAL_PRECISION: Final[int] = 50
MAX_INTEGER_DIGITS: Final[int] = 20
MAX_FRACTIONAL_DIGITS: Final[int] = 18


def ensure_numeric_38_18(value: Decimal, label: str) -> Decimal:
    if not value.is_finite():
        raise ValueError(f"{label} must be finite")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError(f"{label} must be finite")
    fractional_digits = max(-exponent, 0)
    integer_digits = 0 if value.is_zero() else max(value.adjusted() + 1, 0)
    if integer_digits > MAX_INTEGER_DIGITS or fractional_digits > MAX_FRACTIONAL_DIGITS:
        raise ValueError(f"{label} does not fit NUMERIC(38,18)")
    return value


def transaction_usd_delta(transaction: Transaction, usd_rate: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        delta = (transaction.plus - transaction.minus) * usd_rate
    return ensure_numeric_38_18(delta, "USD delta")
