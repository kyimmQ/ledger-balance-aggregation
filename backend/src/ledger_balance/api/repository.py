from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ledger_balance.api.query_models import AccountBalanceSnapshot, TotalBalanceSnapshot
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import AccountBalance, AccountId, CurrencyCode

ACCOUNT_BALANCE_SNAPSHOT_SQL = """
WITH dataset AS (
    SELECT EXISTS (SELECT 1 FROM account_balances) AS dataset_ready
),
currency_state AS (
    SELECT EXISTS (
        SELECT 1 FROM currencies WHERE code = $2
    ) AS currency_supported
),
latest_rate AS (
    SELECT rate_date, usd_rate
    FROM exchange_rates
    WHERE currency_code = $2
      AND $2 <> 'USD'
    ORDER BY rate_date DESC
    LIMIT 1
)
SELECT
    dataset.dataset_ready,
    currency_state.currency_supported,
    account_balances.account_id,
    account_balances.name,
    account_balances.balance_usd,
    latest_rate.usd_rate,
    latest_rate.rate_date AS valuation_date
FROM dataset
CROSS JOIN currency_state
LEFT JOIN account_balances ON account_balances.account_id = $1
LEFT JOIN latest_rate ON TRUE
"""

TOTAL_BALANCE_SNAPSHOT_SQL = """
WITH totals AS (
    SELECT SUM(balance_usd) AS total_usd
    FROM account_balances
),
currency_state AS (
    SELECT EXISTS (
        SELECT 1 FROM currencies WHERE code = $1
    ) AS currency_supported
),
latest_rate AS (
    SELECT rate_date, usd_rate
    FROM exchange_rates
    WHERE currency_code = $1
      AND $1 <> 'USD'
    ORDER BY rate_date DESC
    LIMIT 1
)
SELECT
    totals.total_usd IS NOT NULL AS dataset_ready,
    currency_state.currency_supported,
    totals.total_usd,
    latest_rate.usd_rate,
    latest_rate.rate_date AS valuation_date
FROM totals
CROSS JOIN currency_state
LEFT JOIN latest_rate ON TRUE
"""


class BalanceReadRepository:
    def __init__(self, database: Database, query_timeout_seconds: float | None = None) -> None:
        self._database = database
        self._query_timeout_seconds = query_timeout_seconds

    async def account_snapshot(
        self,
        account_id: AccountId,
        currency: CurrencyCode,
    ) -> AccountBalanceSnapshot:
        async with self._database.connection() as connection:
            row = await connection.fetchrow(
                ACCOUNT_BALANCE_SNAPSHOT_SQL,
                int(account_id),
                str(currency),
                timeout=self._query_timeout_seconds,
            )
        return _account_snapshot(row)

    async def total_snapshot(self, currency: CurrencyCode) -> TotalBalanceSnapshot:
        async with self._database.connection() as connection:
            row = await connection.fetchrow(
                TOTAL_BALANCE_SNAPSHOT_SQL,
                str(currency),
                timeout=self._query_timeout_seconds,
            )
        return _total_snapshot(row)


def _account_snapshot(row: Mapping[str, object] | None) -> AccountBalanceSnapshot:
    values = _required_row(row)
    dataset_ready = _required_bool(values, "dataset_ready")
    currency_supported, usd_rate, valuation_date = _valuation_state(values)

    raw_account_id = _field(values, "account_id")
    raw_name = _field(values, "name")
    raw_balance = _field(values, "balance_usd")
    if raw_account_id is None and raw_name is None and raw_balance is None:
        account = None
    elif (
        isinstance(raw_account_id, int)
        and not isinstance(raw_account_id, bool)
        and isinstance(raw_name, str)
        and isinstance(raw_balance, Decimal)
    ):
        account = AccountBalance(AccountId(raw_account_id), raw_name, raw_balance)
    else:
        raise RuntimeError("account balance query returned invalid account data")

    if not dataset_ready and account is not None:
        raise RuntimeError("account balance query returned inconsistent dataset state")

    return AccountBalanceSnapshot(
        dataset_ready=dataset_ready,
        currency_supported=currency_supported,
        account=account,
        usd_rate=usd_rate,
        valuation_date=valuation_date,
    )


def _total_snapshot(row: Mapping[str, object] | None) -> TotalBalanceSnapshot:
    values = _required_row(row)
    dataset_ready = _required_bool(values, "dataset_ready")
    currency_supported, usd_rate, valuation_date = _valuation_state(values)
    total_usd = _field(values, "total_usd")
    if total_usd is not None and not isinstance(total_usd, Decimal):
        raise RuntimeError("total balance query returned invalid total")
    if dataset_ready != (total_usd is not None):
        raise RuntimeError("total balance query returned inconsistent dataset state")

    return TotalBalanceSnapshot(
        dataset_ready=dataset_ready,
        currency_supported=currency_supported,
        total_usd=total_usd,
        usd_rate=usd_rate,
        valuation_date=valuation_date,
    )


def _required_row(row: Mapping[str, object] | None) -> Mapping[str, object]:
    if row is None:
        raise RuntimeError("balance query returned no row")
    return row


def _required_bool(row: Mapping[str, object], field: str) -> bool:
    value = _field(row, field)
    if not isinstance(value, bool):
        raise RuntimeError(f"balance query returned invalid {field}")
    return value


def _field(row: Mapping[str, object], field: str) -> object:
    try:
        return row[field]
    except KeyError:
        raise RuntimeError(f"balance query did not return {field}") from None


def _valuation_state(
    row: Mapping[str, object],
) -> tuple[bool, Decimal | None, date | None]:
    currency_supported = _required_bool(row, "currency_supported")
    usd_rate = _field(row, "usd_rate")
    valuation_date = _field(row, "valuation_date")

    if usd_rate is not None and (
        not isinstance(usd_rate, Decimal) or not usd_rate.is_finite() or usd_rate <= 0
    ):
        raise RuntimeError("balance query returned invalid valuation rate")
    if valuation_date is not None and not isinstance(valuation_date, date):
        raise RuntimeError("balance query returned invalid valuation date")
    if (usd_rate is None) != (valuation_date is None):
        raise RuntimeError("balance query returned incomplete valuation data")
    if not currency_supported and usd_rate is not None:
        raise RuntimeError("balance query returned a rate for an unsupported currency")

    return currency_supported, usd_rate, valuation_date
