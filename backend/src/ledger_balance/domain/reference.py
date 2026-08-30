from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, localcontext

from ledger_balance.domain.arithmetic import DECIMAL_PRECISION, transaction_usd_delta
from ledger_balance.domain.models import AccountBalance, AccountId, RateBook, Transaction


@dataclass(frozen=True, slots=True)
class ReferenceResult:
    balances: tuple[AccountBalance, ...]
    transaction_count: int
    total_usd: Decimal


def reduce_transactions(
    transactions: Iterable[Transaction], rate_book: RateBook
) -> ReferenceResult:
    names: dict[AccountId, str] = {}
    values: dict[AccountId, Decimal] = {}
    count = 0
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        for transaction in transactions:
            delta = transaction_usd_delta(transaction, rate_book.historical_rate(transaction))
            names[transaction.account_id] = transaction.name
            values[transaction.account_id] = (
                values.get(transaction.account_id, Decimal("0")) + delta
            )
            count += 1
        balances = tuple(
            AccountBalance(account_id, names[account_id], balance)
            for account_id, balance in sorted(values.items())
        )
        total = sum((item.balance_usd for item in balances), start=Decimal("0"))
    return ReferenceResult(balances, count, total)
