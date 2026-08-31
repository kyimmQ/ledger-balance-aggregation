from dataclasses import dataclass
from decimal import Decimal

from ledger_balance.db.pool import Database
from ledger_balance.domain.currencies import USD
from ledger_balance.domain.models import RateBook, Transaction

RESET_SQL = "TRUNCATE TABLE account_balances, exchange_rates, currencies"
CURRENCY_SQL = "INSERT INTO currencies (code) VALUES ($1)"
RATE_SQL = """
INSERT INTO exchange_rates (currency_code, rate_date, usd_rate)
VALUES ($1, $2, $3)
"""
BALANCE_SQL = """
INSERT INTO account_balances (account_id, name, balance_usd)
VALUES ($1, $2, $3)
ON CONFLICT (account_id)
DO UPDATE SET
    name = EXCLUDED.name,
    balance_usd = account_balances.balance_usd + EXCLUDED.balance_usd
"""
STATS_SQL = """
SELECT
  (SELECT count(*) FROM account_balances) AS account_count,
  (SELECT count(*) FROM exchange_rates) AS rate_count,
  COALESCE((SELECT sum(balance_usd) FROM account_balances), 0) AS total_usd
"""


@dataclass(frozen=True, slots=True)
class StoredStats:
    account_count: int
    rate_count: int
    total_usd: Decimal


class LedgerRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def reset(self) -> None:
        async with self._database.connection() as connection:
            await connection.execute(RESET_SQL)

    async def insert_rate_book(self, rate_book: RateBook) -> None:
        currencies = [(str(code),) for code in sorted(rate_book.currencies | {USD})]
        rates = [
            (str(currency), rate_date, usd_rate)
            for (currency, rate_date), usd_rate in sorted(
                rate_book.rates.items(), key=lambda item: (item[0][1], item[0][0])
            )
        ]
        async with self._database.connection() as connection:
            await connection.executemany(CURRENCY_SQL, currencies)
            await connection.executemany(RATE_SQL, rates)

    async def add_balance_delta(self, transaction: Transaction, delta: Decimal) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                BALANCE_SQL,
                int(transaction.account_id),
                transaction.name,
                delta,
            )

    async def stats(self) -> StoredStats:
        async with self._database.connection() as connection:
            row = await connection.fetchrow(STATS_SQL)
        if row is None:
            raise RuntimeError("database statistics query returned no row")
        account_count = row["account_count"]
        rate_count = row["rate_count"]
        total_usd = row["total_usd"]
        if not isinstance(account_count, int) or not isinstance(rate_count, int):
            raise RuntimeError("database statistics returned invalid counts")
        if not isinstance(total_usd, Decimal):
            raise RuntimeError("database statistics returned invalid total")
        return StoredStats(account_count, rate_count, total_usd)
