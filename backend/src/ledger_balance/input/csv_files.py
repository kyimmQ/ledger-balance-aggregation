import csv
from collections.abc import Iterator
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ledger_balance.domain.arithmetic import ensure_numeric_38_18
from ledger_balance.domain.currencies import USD
from ledger_balance.domain.models import (
    AccountId,
    CurrencyCode,
    ExchangeRate,
    RateBook,
    RateKey,
    Transaction,
)
from ledger_balance.input.errors import InputFileError

RATE_HEADERS = ("date", "currency", "rate")
TRANSACTION_HEADERS = ("id", "name", "plus", "minus", "currency", "date")


def load_rates(path: Path) -> RateBook:
    rates: list[ExchangeRate] = []
    seen: set[RateKey] = set()
    for row_number, row in _rows(path, RATE_HEADERS):
        rate_date = _date(path, row_number, "date", _field(row, "date"))
        currency = _currency(path, row_number, "currency", _field(row, "currency"))
        usd_rate = _decimal(path, row_number, "rate", _field(row, "rate"), positive=True)
        if currency == USD and usd_rate != Decimal("1"):
            raise InputFileError(path, row_number, "rate", "USD rate must equal 1")
        key: RateKey = (currency, rate_date)
        if key in seen:
            raise InputFileError(
                path,
                row_number,
                "currency",
                f"duplicate rate for {currency} on {rate_date.isoformat()}",
            )
        seen.add(key)
        rates.append(ExchangeRate(currency=currency, rate_date=rate_date, usd_rate=usd_rate))
    if not rates:
        raise InputFileError(path, 1, "header", "rate file contains no data rows")
    return RateBook.from_rates(rates)


def iter_transactions(path: Path, rate_book: RateBook) -> Iterator[Transaction]:
    names: dict[AccountId, str] = {}
    for row_number, row in _rows(path, TRANSACTION_HEADERS):
        account_id = _account_id(path, row_number, _field(row, "id"))
        name = _name(path, row_number, _field(row, "name"))
        plus = _decimal(path, row_number, "plus", _field(row, "plus"), positive=False)
        minus = _decimal(path, row_number, "minus", _field(row, "minus"), positive=False)
        currency = _currency(path, row_number, "currency", _field(row, "currency"))
        transaction_date = _date(path, row_number, "date", _field(row, "date"))
        if account_id in names and names[account_id] != name:
            raise InputFileError(
                path,
                row_number,
                "name",
                f"inconsistent name for account {account_id}: {name!r} != {names[account_id]!r}",
            )
        transaction = Transaction(
            account_id=account_id,
            name=name,
            plus=plus,
            minus=minus,
            currency=currency,
            transaction_date=transaction_date,
        )
        if (currency, transaction_date) not in rate_book.rates:
            raise InputFileError(
                path,
                row_number,
                "currency",
                f"missing historical rate for {currency} on {transaction_date.isoformat()}",
            )
        names[account_id] = name
        yield transaction


def _rows(path: Path, expected_headers: tuple[str, ...]) -> Iterator[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        actual = tuple(reader.fieldnames or ())
        if actual != expected_headers:
            got = ",".join(part or "" for part in actual)
            raise InputFileError(
                path,
                1,
                "header",
                f"expected {','.join(expected_headers)}, got {got}",
            )
        yield from enumerate(reader, start=2)


def _field(row: dict[str, str], name: str) -> str:
    value = row[name]
    return "" if value is None else value


def _currency(path: Path, row: int, field: str, raw: str) -> CurrencyCode:
    value = raw.strip().upper()
    if not (3 <= len(value) <= 8 and value.isascii() and value.isalpha()):
        raise InputFileError(path, row, field, "must be 3 to 8 ASCII letters")
    return CurrencyCode(value)


def _date(path: Path, row: int, field: str, raw: str) -> date:
    text = raw.strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise InputFileError(path, row, field, "invalid date") from None
    if parsed.isoformat() != text:
        raise InputFileError(path, row, field, "must be canonical YYYY-MM-DD")
    return parsed


def _decimal(path: Path, row: int, field: str, raw: str, *, positive: bool) -> Decimal:
    text = raw.strip()
    if text == "":
        raise InputFileError(path, row, field, "must not be blank")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise InputFileError(path, row, field, "invalid decimal") from None
    if not value.is_finite():
        raise InputFileError(path, row, field, "must be finite")
    if positive:
        if value <= 0:
            raise InputFileError(path, row, field, "must be positive")
    elif value < 0:
        raise InputFileError(path, row, field, "must be nonnegative")
    try:
        return ensure_numeric_38_18(value, field)
    except ValueError:
        raise InputFileError(path, row, field, "does not fit NUMERIC(38,18)") from None


def _account_id(path: Path, row: int, raw: str) -> AccountId:
    text = raw.strip()
    try:
        value = int(text)
    except ValueError:
        raise InputFileError(path, row, "id", "must be an integer") from None
    if value < 100 or value > 999:
        raise InputFileError(path, row, "id", "must be between 100 and 999")
    return AccountId(value)


def _name(path: Path, row: int, raw: str) -> str:
    value = raw.strip()
    if value == "":
        raise InputFileError(path, row, "name", "must not be blank")
    if len(value) > 255:
        raise InputFileError(path, row, "name", "must be at most 255 characters")
    return value
