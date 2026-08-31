import re
from typing import Protocol, cast

import asyncpg  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Query, Request

from ledger_balance.api.auth import require_api_key
from ledger_balance.api.contracts import AccountBalanceResponse, TotalBalanceResponse
from ledger_balance.api.conversion import convert_usd, format_money
from ledger_balance.api.errors import (
    AccountNotFoundError,
    DatabaseTimeoutError,
    DatabaseUnavailableError,
    DatasetNotReadyError,
    InvalidAccountIdError,
    InvalidCurrencyError,
    UnsupportedCurrencyError,
    ValuationRateUnavailableApiError,
    ValuationRateUnavailableError,
)
from ledger_balance.api.query_models import AccountBalanceSnapshot, TotalBalanceSnapshot
from ledger_balance.api.rate_limit import enforce_rate_limit
from ledger_balance.domain.currencies import USD
from ledger_balance.domain.models import AccountId, CurrencyCode

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3,8}$")
_ACCOUNT_PATTERN = re.compile(r"^[0-9]+$")


class ReadRepository(Protocol):
    async def account_snapshot(
        self, account_id: AccountId, currency: CurrencyCode
    ) -> AccountBalanceSnapshot: ...

    async def total_snapshot(self, currency: CurrencyCode) -> TotalBalanceSnapshot: ...


router = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)


def repository_from_request(request: Request) -> ReadRepository:
    return cast(ReadRepository, request.app.state.read_repository)


def normalize_currency(raw: str | None) -> CurrencyCode:
    if raw is None:
        return USD
    normalized = raw.strip().upper()
    if _CURRENCY_PATTERN.fullmatch(normalized) is None:
        raise InvalidCurrencyError()
    return CurrencyCode(normalized)


def parse_account_id(raw: str) -> AccountId:
    if _ACCOUNT_PATTERN.fullmatch(raw) is None:
        raise InvalidAccountIdError(raw)
    try:
        value = int(raw)
    except ValueError as error:
        raise InvalidAccountIdError(raw) from error
    if not 100 <= value <= 999:
        raise InvalidAccountIdError(raw)
    return AccountId(value)


def _classify_dataset(snapshot: AccountBalanceSnapshot | TotalBalanceSnapshot) -> None:
    if not snapshot.dataset_ready:
        raise DatasetNotReadyError()


def _classify_currency(snapshot: AccountBalanceSnapshot | TotalBalanceSnapshot) -> None:
    if not snapshot.currency_supported:
        raise UnsupportedCurrencyError("requested currency")


async def _account_snapshot(
    repository: ReadRepository,
    account_id: AccountId,
    currency: CurrencyCode,
) -> AccountBalanceSnapshot:
    try:
        return await repository.account_snapshot(account_id, currency)
    except TimeoutError as error:
        raise DatabaseTimeoutError() from error
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as error:
        raise DatabaseUnavailableError() from error


async def _total_snapshot(
    repository: ReadRepository,
    currency: CurrencyCode,
) -> TotalBalanceSnapshot:
    try:
        return await repository.total_snapshot(currency)
    except TimeoutError as error:
        raise DatabaseTimeoutError() from error
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as error:
        raise DatabaseUnavailableError() from error


@router.get(
    "/accounts/{account_id}/balance",
    response_model=AccountBalanceResponse,
    response_model_by_alias=True,
)
async def account_balance(
    account_id: str,
    currency: str | None = Query(default=None),
    repository: ReadRepository = Depends(repository_from_request),  # noqa: B008
) -> AccountBalanceResponse:
    parsed_account_id = parse_account_id(account_id)
    requested_currency = normalize_currency(currency)
    snapshot = await _account_snapshot(repository, parsed_account_id, requested_currency)
    _classify_dataset(snapshot)
    _classify_currency(snapshot)
    if snapshot.account is None:
        raise AccountNotFoundError(int(parsed_account_id))
    try:
        amount = convert_usd(snapshot.account.balance_usd, requested_currency, snapshot.usd_rate)
    except ValuationRateUnavailableError as error:
        raise ValuationRateUnavailableApiError(str(requested_currency)) from error
    return AccountBalanceResponse(
        accountId=int(snapshot.account.account_id),
        name=snapshot.account.name,
        currency=str(requested_currency),
        balance=format_money(amount),
        valuationDate=None if requested_currency == USD else snapshot.valuation_date,
    )


@router.get(
    "/balances/total",
    response_model=TotalBalanceResponse,
    response_model_by_alias=True,
)
async def total_balance(
    currency: str | None = Query(default=None),
    repository: ReadRepository = Depends(repository_from_request),  # noqa: B008
) -> TotalBalanceResponse:
    requested_currency = normalize_currency(currency)
    snapshot = await _total_snapshot(repository, requested_currency)
    _classify_dataset(snapshot)
    _classify_currency(snapshot)
    if snapshot.total_usd is None:
        raise DatasetNotReadyError()
    try:
        amount = convert_usd(snapshot.total_usd, requested_currency, snapshot.usd_rate)
    except ValuationRateUnavailableError as error:
        raise ValuationRateUnavailableApiError(str(requested_currency)) from error
    return TotalBalanceResponse(
        currency=str(requested_currency),
        total=format_money(amount),
        valuationDate=None if requested_currency == USD else snapshot.valuation_date,
    )
