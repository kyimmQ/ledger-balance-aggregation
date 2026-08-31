from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ledger_balance.domain.models import AccountBalance


@dataclass(frozen=True, slots=True)
class AccountBalanceSnapshot:
    dataset_ready: bool
    currency_supported: bool
    account: AccountBalance | None
    usd_rate: Decimal | None
    valuation_date: date | None


@dataclass(frozen=True, slots=True)
class TotalBalanceSnapshot:
    dataset_ready: bool
    currency_supported: bool
    total_usd: Decimal | None
    usd_rate: Decimal | None
    valuation_date: date | None
