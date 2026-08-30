import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from ledger_balance.domain.models import AccountId, CurrencyCode, RateBook, Transaction
from ledger_balance.input.csv_files import (
    RATE_HEADERS,
    TRANSACTION_HEADERS,
    iter_transactions,
    load_rates,
)
from ledger_balance.input.errors import InputFileError


def write_csv(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def rates_text(*rows: str) -> str:
    return "date,currency,rate\n" + "".join(f"{row}\n" for row in rows)


def transactions_text(*rows: str) -> str:
    return "id,name,plus,minus,currency,date\n" + "".join(f"{row}\n" for row in rows)


def check_input_error(
    error: InputFileError,
    *,
    path: Path,
    row: int,
    field: str,
    message: str,
) -> None:
    assert error.path == path
    assert error.row == row
    assert error.field == field
    assert error.message == message
    assert str(error) == f"{path}:{row}: field '{field}': {message}"


def valid_rate_book(tmp_path: Path) -> RateBook:
    return load_rates(
        write_csv(
            tmp_path,
            "rates.csv",
            rates_text("2026-06-15,USD,1", "2026-06-15,EUR,1.0832", "2026-06-16,EUR,1.0803"),
        )
    )


def test_load_rates_and_iter_transactions(tmp_path: Path) -> None:
    rate_path = write_csv(
        tmp_path,
        "rates.csv",
        rates_text("2026-06-15,USD,1.0", "2026-06-15,eur,1.0832", "2026-06-16,EUR,1.0803"),
    )
    tx_path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(
            "100,acct100,250.00,120.50,USD,2026-06-15",
            "243,acct243,80.00,0.00,eur,2026-06-16",
            "100,acct100,15.25,60.00,EUR,2026-06-15",
        ),
    )

    rate_book = load_rates(rate_path)
    transactions = list(iter_transactions(tx_path, rate_book))

    assert rate_book.currencies == frozenset({CurrencyCode("USD"), CurrencyCode("EUR")})
    assert rate_book.rates[(CurrencyCode("USD"), date(2026, 6, 15))] == Decimal("1.0")
    assert rate_book.rates[(CurrencyCode("EUR"), date(2026, 6, 15))] == Decimal("1.0832")
    assert transactions == [
        Transaction(
            account_id=AccountId(100),
            name="acct100",
            plus=Decimal("250.00"),
            minus=Decimal("120.50"),
            currency=CurrencyCode("USD"),
            transaction_date=date(2026, 6, 15),
        ),
        Transaction(
            account_id=AccountId(243),
            name="acct243",
            plus=Decimal("80.00"),
            minus=Decimal("0.00"),
            currency=CurrencyCode("EUR"),
            transaction_date=date(2026, 6, 16),
        ),
        Transaction(
            account_id=AccountId(100),
            name="acct100",
            plus=Decimal("15.25"),
            minus=Decimal("60.00"),
            currency=CurrencyCode("EUR"),
            transaction_date=date(2026, 6, 15),
        ),
    ]


def test_eur_only_rate_file_without_usd_is_allowed(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "rates.csv", rates_text("2026-06-15,EUR,1.0832"))

    rate_book = load_rates(path)

    assert rate_book.currencies == frozenset({CurrencyCode("EUR")})
    assert (CurrencyCode("USD"), date(2026, 6, 15)) not in rate_book.rates


def test_iter_transactions_is_a_generator(tmp_path: Path) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text("100,acct100,1.00,0.00,USD,2026-06-15"),
    )

    iterator = iter_transactions(path, rate_book)

    assert inspect.isgeneratorfunction(iter_transactions)
    assert inspect.isgenerator(iterator)
    assert not isinstance(iterator, list)


@pytest.mark.parametrize(
    "header",
    [
        "currency,date,rate",
        "date,currency",
        "date,currency,rate,extra",
        "Date,currency,rate",
    ],
)
def test_rate_headers_must_match_exactly(tmp_path: Path, header: str) -> None:
    path = write_csv(tmp_path, "rates.csv", f"{header}\n2026-06-15,USD,1\n")

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(
        caught.value,
        path=path,
        row=1,
        field="header",
        message=f"expected {','.join(RATE_HEADERS)}, got {header}",
    )


@pytest.mark.parametrize(
    "header",
    [
        "name,id,plus,minus,currency,date",
        "id,name,plus,minus,currency",
        "id,name,plus,minus,currency,date,extra",
        "ID,name,plus,minus,currency,date",
    ],
)
def test_transaction_headers_must_match_exactly(tmp_path: Path, header: str) -> None:
    path = write_csv(
        tmp_path, "transactions.csv", f"{header}\n100,acct100,1.00,0.00,USD,2026-06-15\n"
    )

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, RateBook.from_rates([])))

    check_input_error(
        caught.value,
        path=path,
        row=1,
        field="header",
        message=f"expected {','.join(TRANSACTION_HEADERS)}, got {header}",
    )


def test_empty_rate_data_is_rejected(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "rates.csv", "date,currency,rate\n")

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(
        caught.value,
        path=path,
        row=1,
        field="header",
        message="rate file contains no data rows",
    )


@pytest.mark.parametrize(
    ("raw_date", "message"),
    [
        ("2026/06/15", "invalid date"),
        ("not-a-date", "invalid date"),
        ("2026-6-15", "invalid date"),
        ("20260615", "must be canonical YYYY-MM-DD"),
        ("2026-W25-1", "must be canonical YYYY-MM-DD"),
    ],
)
def test_malformed_and_noncanonical_rate_dates(tmp_path: Path, raw_date: str, message: str) -> None:
    path = write_csv(tmp_path, "rates.csv", rates_text(f"{raw_date},USD,1"))

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(caught.value, path=path, row=2, field="date", message=message)


@pytest.mark.parametrize(
    ("raw_date", "message"),
    [
        ("2026/06/15", "invalid date"),
        ("2026-6-15", "invalid date"),
        ("20260615", "must be canonical YYYY-MM-DD"),
    ],
)
def test_malformed_and_noncanonical_transaction_dates(
    tmp_path: Path, raw_date: str, message: str
) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(f"100,acct100,1.00,0.00,USD,{raw_date}"),
    )

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, rate_book))

    check_input_error(caught.value, path=path, row=2, field="date", message=message)


@pytest.mark.parametrize(
    "raw_currency",
    ["US", "ABCDEFGHI", "US1", "US-D", ""],
)
def test_invalid_rate_currency(tmp_path: Path, raw_currency: str) -> None:
    path = write_csv(tmp_path, "rates.csv", rates_text(f"2026-06-15,{raw_currency},1"))

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(
        caught.value,
        path=path,
        row=2,
        field="currency",
        message="must be 3 to 8 ASCII letters",
    )


def test_account_id_must_be_an_integer(tmp_path: Path) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text("abc,acct100,1.00,0.00,USD,2026-06-15"),
    )

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, rate_book))

    check_input_error(caught.value, path=path, row=2, field="id", message="must be an integer")


@pytest.mark.parametrize("account_id", ["99", "1000"])
def test_account_id_must_be_in_range(tmp_path: Path, account_id: str) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(f"{account_id},acct100,1.00,0.00,USD,2026-06-15"),
    )

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, rate_book))

    check_input_error(
        caught.value,
        path=path,
        row=2,
        field="id",
        message="must be between 100 and 999",
    )


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_is_rejected(tmp_path: Path, name: str) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(f"100,{name},1.00,0.00,USD,2026-06-15"),
    )

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, rate_book))

    check_input_error(caught.value, path=path, row=2, field="name", message="must not be blank")


def test_name_longer_than_255_is_rejected(tmp_path: Path) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(f"100,{'a' * 256},1.00,0.00,USD,2026-06-15"),
    )

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, rate_book))

    check_input_error(
        caught.value,
        path=path,
        row=2,
        field="name",
        message="must be at most 255 characters",
    )


def test_repeated_account_name_mismatch(tmp_path: Path) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(
            "100,acct100,1.00,0.00,USD,2026-06-15",
            "100,other,1.00,0.00,USD,2026-06-15",
        ),
    )
    iterator = iter_transactions(path, rate_book)

    assert next(iterator).name == "acct100"
    with pytest.raises(InputFileError) as caught:
        next(iterator)

    check_input_error(
        caught.value,
        path=path,
        row=3,
        field="name",
        message="inconsistent name for account 100: 'other' != 'acct100'",
    )


def test_quoted_comma_in_name(tmp_path: Path) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        'id,name,plus,minus,currency,date\n100,"Smith, John",10.00,0.00,USD,2026-06-15\n',
    )

    [transaction] = list(iter_transactions(path, rate_book))

    assert transaction.name == "Smith, John"


@pytest.mark.parametrize(
    ("row", "field", "message"),
    [
        ("100,acct100,abc,0.00,USD,2026-06-15", "plus", "invalid decimal"),
        ("100,acct100,,0.00,USD,2026-06-15", "plus", "must not be blank"),
        ("100,acct100,NaN,0.00,USD,2026-06-15", "plus", "must be finite"),
        ("100,acct100,Infinity,0.00,USD,2026-06-15", "plus", "must be finite"),
        ("100,acct100,-Infinity,0.00,USD,2026-06-15", "plus", "must be finite"),
        ("100,acct100,-1.00,0.00,USD,2026-06-15", "plus", "must be nonnegative"),
        ("100,acct100,0.00,-1.00,USD,2026-06-15", "minus", "must be nonnegative"),
        (
            "100,acct100," + ("1" + "0" * 20) + ",0.00,USD,2026-06-15",
            "plus",
            "does not fit NUMERIC(38,18)",
        ),
        (
            "100,acct100,0." + ("0" * 18) + "1,0.00,USD,2026-06-15",
            "plus",
            "does not fit NUMERIC(38,18)",
        ),
    ],
)
def test_invalid_amounts(tmp_path: Path, row: str, field: str, message: str) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(tmp_path, "transactions.csv", transactions_text(row))

    with pytest.raises(InputFileError) as caught:
        next(iter_transactions(path, rate_book))

    check_input_error(caught.value, path=path, row=2, field=field, message=message)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("2026-06-15,USD,abc", "invalid decimal"),
        ("2026-06-15,USD,", "must not be blank"),
        ("2026-06-15,USD,NaN", "must be finite"),
        ("2026-06-15,USD,0", "must be positive"),
        ("2026-06-15,USD,-1", "must be positive"),
        ("2026-06-15,EUR," + ("1" + "0" * 20), "does not fit NUMERIC(38,18)"),
    ],
)
def test_nonpositive_and_invalid_rates(tmp_path: Path, row: str, message: str) -> None:
    path = write_csv(tmp_path, "rates.csv", rates_text(row))

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(caught.value, path=path, row=2, field="rate", message=message)


def test_duplicate_rate_keys_are_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "rates.csv",
        rates_text("2026-06-15,EUR,1.0832", "2026-06-15,EUR,1.0803"),
    )

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(
        caught.value,
        path=path,
        row=3,
        field="currency",
        message="duplicate rate for EUR on 2026-06-15",
    )


def test_each_usd_rate_must_equal_one(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path,
        "rates.csv",
        rates_text("2026-06-15,USD,1", "2026-06-16,USD,1.1"),
    )

    with pytest.raises(InputFileError) as caught:
        load_rates(path)

    check_input_error(
        caught.value,
        path=path,
        row=3,
        field="rate",
        message="USD rate must equal 1",
    )


def test_missing_historical_rate_fails_before_yield(tmp_path: Path) -> None:
    rate_book = load_rates(write_csv(tmp_path, "rates.csv", rates_text("2026-06-15,EUR,1.0832")))
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(
            "100,acct100,1.00,0.00,EUR,2026-06-15",
            "101,acct101,1.00,0.00,USD,2026-06-15",
        ),
    )
    iterator = iter_transactions(path, rate_book)

    first = next(iterator)
    assert first.account_id == AccountId(100)
    with pytest.raises(InputFileError) as caught:
        next(iterator)

    check_input_error(
        caught.value,
        path=path,
        row=3,
        field="currency",
        message="missing historical rate for USD on 2026-06-15",
    )


def test_fail_fast_allows_consuming_a_valid_row_before_later_error(tmp_path: Path) -> None:
    rate_book = valid_rate_book(tmp_path)
    path = write_csv(
        tmp_path,
        "transactions.csv",
        transactions_text(
            "100,acct100,1.00,0.00,USD,2026-06-15",
            "101,acct101,not-a-number,0.00,USD,2026-06-15",
        ),
    )
    iterator = iter_transactions(path, rate_book)

    first = next(iterator)
    assert first.account_id == AccountId(100)
    with pytest.raises(InputFileError) as caught:
        next(iterator)

    check_input_error(
        caught.value,
        path=path,
        row=3,
        field="plus",
        message="invalid decimal",
    )


def test_unreadable_files_raise_oserror_not_input_file_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"

    with pytest.raises(OSError):
        load_rates(missing)
    with pytest.raises(OSError):
        next(iter_transactions(missing, RateBook.from_rates([])))
