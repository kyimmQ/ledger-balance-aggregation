from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import NewType

AccountId = NewType("AccountId", int)
CurrencyCode = NewType("CurrencyCode", str)
RateKey = tuple[CurrencyCode, date]


@dataclass(frozen=True, slots=True)
class Transaction:
    account_id: AccountId
    name: str
    plus: Decimal
    minus: Decimal
    currency: CurrencyCode
    transaction_date: date


@dataclass(frozen=True, slots=True)
class ExchangeRate:
    currency: CurrencyCode
    rate_date: date
    usd_rate: Decimal

    @property
    def key(self) -> RateKey:
        return (self.currency, self.rate_date)


@dataclass(frozen=True, slots=True)
class AccountBalance:
    account_id: AccountId
    name: str
    balance_usd: Decimal


@dataclass(frozen=True, slots=True)
class RateBook:
    rates: Mapping[RateKey, Decimal]
    currencies: frozenset[CurrencyCode]

    @classmethod
    def from_rates(cls, rates: list[ExchangeRate]) -> "RateBook":
        values = {rate.key: rate.usd_rate for rate in rates}
        return cls(
            MappingProxyType(values),
            frozenset(rate.currency for rate in rates),
        )

    def historical_rate(self, transaction: Transaction) -> Decimal:
        return self.rates[(transaction.currency, transaction.transaction_date)]
