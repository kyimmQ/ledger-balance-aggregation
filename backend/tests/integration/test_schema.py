from datetime import date
from decimal import Decimal

import asyncpg  # type: ignore[import-untyped]
import pytest

pytestmark = pytest.mark.integration

EXPECTED_COLUMNS = {
    "currencies": {
        "code": ("character varying", None, None, 8),
    },
    "exchange_rates": {
        "currency_code": ("character varying", None, None, 8),
        "rate_date": ("date", None, None, None),
        "usd_rate": ("numeric", 38, 18, None),
    },
    "account_balances": {
        "account_id": ("integer", 32, 0, None),
        "name": ("character varying", None, None, 255),
        "balance_usd": ("numeric", 38, 18, None),
    },
}

EXPECTED_CONSTRAINTS = {
    "pk_currencies": ("p", "PRIMARY KEY (code)"),
    "ck_currencies_code_format": ("c", "CHECK (((code)::text ~ '^[A-Z]{3,8}$'::text))"),
    "pk_exchange_rates": ("p", "PRIMARY KEY (currency_code, rate_date)"),
    "ck_exchange_rates_positive": ("c", "CHECK ((usd_rate > (0)::numeric))"),
    "fk_exchange_rates_currency": (
        "f",
        "FOREIGN KEY (currency_code) REFERENCES currencies(code) ON DELETE CASCADE",
    ),
    "pk_account_balances": ("p", "PRIMARY KEY (account_id)"),
    "ck_account_balances_id_range": (
        "c",
        "CHECK (((account_id >= 100) AND (account_id <= 999)))",
    ),
    "ck_account_balances_name_nonempty": (
        "c",
        "CHECK ((char_length(btrim((name)::text)) > 0))",
    ),
}


async def test_schema_shape(db_connection: asyncpg.Connection) -> None:
    tables = await db_connection.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name <> 'alembic_version'
        """
    )
    assert {row["table_name"] for row in tables} == set(EXPECTED_COLUMNS)

    columns = await db_connection.fetch(
        """
        SELECT table_name, column_name, data_type, numeric_precision,
               numeric_scale, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY($1::text[])
        """,
        list(EXPECTED_COLUMNS),
    )
    actual_columns: dict[str, dict[str, tuple[object, object, object, object]]] = {
        table: {} for table in EXPECTED_COLUMNS
    }
    for row in columns:
        assert row["is_nullable"] == "NO"
        actual_columns[row["table_name"]][row["column_name"]] = (
            row["data_type"],
            row["numeric_precision"],
            row["numeric_scale"],
            row["character_maximum_length"],
        )
    assert actual_columns == EXPECTED_COLUMNS

    constraints = await db_connection.fetch(
        """
        SELECT con.conname, con.contype::text AS constraint_type,
               pg_get_constraintdef(con.oid) AS definition
        FROM pg_constraint AS con
        JOIN pg_class AS rel ON rel.oid = con.conrelid
        JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace
        WHERE namespace.nspname = 'public'
          AND rel.relname = ANY($1::text[])
        """,
        list(EXPECTED_COLUMNS),
    )
    assert {
        row["conname"]: (row["constraint_type"], row["definition"]) for row in constraints
    } == EXPECTED_CONSTRAINTS


async def test_currency_format_constraint(db_connection: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await db_connection.execute("INSERT INTO currencies (code) VALUES ('usd')")


async def test_rate_foreign_key_constraint(db_connection: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await db_connection.execute(
            """
            INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
            VALUES ('EUR', '2026-06-15', 1.1)
            """
        )


async def test_rate_primary_key_constraint(db_connection: asyncpg.Connection) -> None:
    await db_connection.execute("INSERT INTO currencies (code) VALUES ('EUR')")
    await db_connection.execute(
        """
        INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
        VALUES ('EUR', '2026-06-15', 1.1)
        """
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await db_connection.execute(
            """
            INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
            VALUES ('EUR', '2026-06-15', 1.2)
            """
        )


@pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-0.1")])
async def test_rate_must_be_positive(db_connection: asyncpg.Connection, rate: Decimal) -> None:
    await db_connection.execute("INSERT INTO currencies (code) VALUES ('EUR')")

    with pytest.raises(asyncpg.CheckViolationError):
        await db_connection.execute(
            """
            INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
            VALUES ('EUR', '2026-06-15', $1)
            """,
            rate,
        )


@pytest.mark.parametrize("account_id", [99, 1000])
async def test_account_id_range_constraint(
    db_connection: asyncpg.Connection, account_id: int
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await db_connection.execute(
            """
            INSERT INTO account_balances (account_id, name, balance_usd)
            VALUES ($1, 'Cash', 0)
            """,
            account_id,
        )


@pytest.mark.parametrize("name", ["", "   "])
async def test_account_name_nonempty_constraint(
    db_connection: asyncpg.Connection, name: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await db_connection.execute(
            """
            INSERT INTO account_balances (account_id, name, balance_usd)
            VALUES (100, $1, 0)
            """,
            name,
        )


async def test_numeric_round_trip_is_exact_decimal(
    db_connection: asyncpg.Connection,
) -> None:
    expected = Decimal("12345678901234567890.123456789012345678")
    await db_connection.execute(
        """
        INSERT INTO account_balances (account_id, name, balance_usd)
        VALUES (100, 'Cash', $1)
        """,
        expected,
    )

    actual = await db_connection.fetchval(
        "SELECT balance_usd FROM account_balances WHERE account_id = 100"
    )

    assert isinstance(actual, Decimal)
    assert actual == expected


async def test_currency_delete_cascades_to_rates(
    db_connection: asyncpg.Connection,
) -> None:
    await db_connection.execute("INSERT INTO currencies (code) VALUES ('EUR')")
    await db_connection.execute(
        """
        INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
        VALUES ('EUR', $1, 1.1)
        """,
        date(2026, 6, 15),
    )

    await db_connection.execute("DELETE FROM currencies WHERE code = 'EUR'")

    assert await db_connection.fetchval("SELECT count(*) FROM exchange_rates") == 0
