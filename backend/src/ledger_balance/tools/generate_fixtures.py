import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Final, Literal, cast

DEFAULT_CURRENCIES: Final[tuple[str, ...]] = ("USD", "EUR", "GBP", "JPY", "SGD")
BASE_RATES: Final[dict[str, Decimal]] = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.0832"),
    "GBP": Decimal("1.2710"),
    "JPY": Decimal("0.00642"),
    "SGD": Decimal("0.7395"),
}
RATE_QUANTUM: Final[Decimal] = Decimal("0.00000001")
ZERO: Final[Decimal] = Decimal("0.00")
TRAP_AMOUNTS: Final[tuple[Decimal, ...]] = (
    Decimal("0.10"),
    Decimal("0.20"),
    Decimal("0.30"),
    Decimal("0.70"),
    Decimal("1.10"),
    Decimal("250.00"),
)
RATIO_SCALE: Final[int] = 10_000

EntryMode = Literal["mixed", "credit-only", "debit-only", "cancel-pairs"]
AccountDistribution = Literal["uniform", "pareto", "hotspot"]
RowOrder = Literal["interleaved", "by-account", "by-date"]


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    output_dir: Path
    rows: int = 50_000
    accounts: int = 900
    dates: int = 10
    seed: int = 20_260_830
    start_date: date = date(2026, 6, 15)
    currencies: tuple[str, ...] = DEFAULT_CURRENCIES
    min_amount: Decimal = Decimal("0.01")
    max_amount: Decimal = Decimal("10000.00")
    entry_mode: EntryMode = "mixed"
    dual_entry_ratio: Decimal = ZERO
    zero_delta_ratio: Decimal = ZERO
    account_distribution: AccountDistribution = "uniform"
    hot_account_ratio: Decimal = Decimal("0.90")
    pareto_head_count: int = 10
    pareto_head_ratio: Decimal = Decimal("0.80")
    order: RowOrder = "interleaved"
    trap_amount_ratio: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class TransactionRow:
    account_id: int
    name: str
    plus: Decimal
    minus: Decimal
    currency: str
    transaction_date: date


RateKey = tuple[str, date]


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." not in text:
        return f"{text}.0"
    stripped = text.rstrip("0").rstrip(".")
    return f"{stripped}.0" if "." not in stripped else stripped


def parse_currencies(raw: str) -> tuple[str, ...]:
    return tuple(code.strip().upper() for code in raw.split(",") if code.strip())


def below_ratio(rng: random.Random, ratio: Decimal) -> bool:
    if ratio <= 0:
        return False
    if ratio >= 1:
        return True
    return Decimal(rng.randrange(RATIO_SCALE)) / Decimal(RATIO_SCALE) < ratio


def generate_rates(config: GeneratorConfig, rng: random.Random) -> dict[RateKey, Decimal]:
    dates = [config.start_date + timedelta(days=offset) for offset in range(config.dates)]
    rates: dict[RateKey, Decimal] = {}
    for index, currency in enumerate(config.currencies):
        for rate_date in dates:
            if currency == "USD":
                rate = Decimal("1.00000000")
            else:
                base = BASE_RATES.get(currency, Decimal(index + 1) / Decimal("2"))
                movement = Decimal(rng.randint(-500, 500)) / Decimal("100000")
                rate = (base * (Decimal("1") + movement)).quantize(RATE_QUANTUM)
            rates[(currency, rate_date)] = rate
    return rates


def choose_account(config: GeneratorConfig, rng: random.Random, row_index: int) -> int:
    if config.account_distribution == "hotspot":
        if config.accounts == 1 or below_ratio(rng, config.hot_account_ratio):
            return 100
        return 101 + rng.randrange(config.accounts - 1)
    if config.account_distribution == "pareto":
        head = min(config.pareto_head_count, config.accounts)
        if below_ratio(rng, config.pareto_head_ratio):
            return 100 + rng.randrange(max(head, 1))
        tail = config.accounts - head
        if tail <= 0:
            return 100 + rng.randrange(config.accounts)
        return 100 + head + rng.randrange(tail)
    if row_index < config.accounts:
        return 100 + row_index
    return 100 + rng.randrange(config.accounts)


def random_amount(config: GeneratorConfig, rng: random.Random) -> Decimal:
    if below_ratio(rng, config.trap_amount_ratio):
        return rng.choice(TRAP_AMOUNTS)
    min_cents = int(config.min_amount * 100)
    max_cents = int(config.max_amount * 100)
    if max_cents < min_cents:
        max_cents = min_cents
    return Decimal(rng.randint(min_cents, max_cents)) / Decimal("100")


def choose_plus_minus(config: GeneratorConfig, rng: random.Random) -> tuple[Decimal, Decimal]:
    if below_ratio(rng, config.zero_delta_ratio):
        if rng.randrange(2) == 0:
            return ZERO, ZERO
        amount = random_amount(config, rng)
        return amount, amount
    if below_ratio(rng, config.dual_entry_ratio):
        return random_amount(config, rng), random_amount(config, rng)
    amount = random_amount(config, rng)
    if config.entry_mode == "credit-only":
        return amount, ZERO
    if config.entry_mode == "debit-only":
        return ZERO, amount
    if rng.randrange(2) == 0:
        return amount, ZERO
    return ZERO, amount


def order_rows(config: GeneratorConfig, rows: list[TransactionRow]) -> list[TransactionRow]:
    if config.order == "by-account":
        return sorted(rows, key=lambda row: (row.account_id, row.transaction_date, row.currency))
    if config.order == "by-date":
        return sorted(rows, key=lambda row: (row.transaction_date, row.account_id, row.currency))
    return rows


def generate_transactions(
    config: GeneratorConfig,
    rng: random.Random,
    rate_keys: tuple[RateKey, ...],
) -> list[TransactionRow]:
    rows: list[TransactionRow] = []
    if config.entry_mode == "cancel-pairs":
        pair_count = config.rows // 2
        for index in range(pair_count):
            account_id = choose_account(config, rng, index)
            currency, transaction_date = rng.choice(rate_keys)
            amount = random_amount(config, rng)
            name = f"acct{account_id}"
            rows.append(TransactionRow(account_id, name, amount, ZERO, currency, transaction_date))
            rows.append(TransactionRow(account_id, name, ZERO, amount, currency, transaction_date))
        if config.rows % 2 == 1:
            account_id = choose_account(config, rng, pair_count)
            currency, transaction_date = rng.choice(rate_keys)
            rows.append(
                TransactionRow(
                    account_id,
                    f"acct{account_id}",
                    ZERO,
                    ZERO,
                    currency,
                    transaction_date,
                )
            )
        return order_rows(config, rows)

    for row_index in range(config.rows):
        account_id = choose_account(config, rng, row_index)
        currency, transaction_date = rng.choice(rate_keys)
        plus, minus = choose_plus_minus(config, rng)
        rows.append(
            TransactionRow(
                account_id,
                f"acct{account_id}",
                plus,
                minus,
                currency,
                transaction_date,
            )
        )
    return order_rows(config, rows)


def calculate_balances(
    transactions: list[TransactionRow], rates: dict[RateKey, Decimal]
) -> dict[int, Decimal]:
    balances: dict[int, Decimal] = {}
    with localcontext() as context:
        context.prec = 50
        for transaction in transactions:
            rate = rates[(transaction.currency, transaction.transaction_date)]
            delta = (transaction.plus - transaction.minus) * rate
            balances[transaction.account_id] = (
                balances.get(transaction.account_id, Decimal("0")) + delta
            )
    return balances


def write_outputs(
    config: GeneratorConfig,
    transactions: list[TransactionRow],
    rates: dict[RateKey, Decimal],
    balances: dict[int, Decimal],
) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    with (config.output_dir / "transactions.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("id", "name", "plus", "minus", "currency", "date"))
        for row in transactions:
            writer.writerow(
                (
                    row.account_id,
                    row.name,
                    f"{row.plus:.2f}",
                    f"{row.minus:.2f}",
                    row.currency,
                    row.transaction_date.isoformat(),
                )
            )
    with (config.output_dir / "exchange_rates.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("date", "currency", "rate"))
        for (currency, rate_date), rate in sorted(
            rates.items(), key=lambda item: (item[0][1], item[0][0])
        ):
            writer.writerow((rate_date.isoformat(), currency, f"{rate:.8f}"))
    with (config.output_dir / "expected_balances.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("id", "name", "balance_usd"))
        for account_id, balance in sorted(balances.items()):
            writer.writerow((account_id, f"acct{account_id}", decimal_text(balance)))
    total = sum(balances.values(), start=Decimal("0"))
    summary = (
        ("seed", str(config.seed)),
        ("transaction_count", str(len(transactions))),
        ("account_count", str(len(balances))),
        ("rate_count", str(len(rates))),
        ("total_balance_usd", decimal_text(total)),
    )
    with (config.output_dir / "expected_summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("key", "value"))
        writer.writerows(summary)


def generate(config: GeneratorConfig) -> None:
    rng = random.Random(config.seed)
    rates = generate_rates(config, rng)
    rate_keys = tuple(sorted(rates, key=lambda item: (item[1], item[0])))
    transactions = generate_transactions(config, rng, rate_keys)
    balances = calculate_balances(transactions, rates)
    write_outputs(config, transactions, rates, balances)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic ledger CSV fixtures")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--accounts", type=int, default=900)
    parser.add_argument("--dates", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20_260_830)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 6, 15))
    parser.add_argument("--currencies", type=parse_currencies, default=DEFAULT_CURRENCIES)
    parser.add_argument("--min-amount", type=Decimal, default=Decimal("0.01"))
    parser.add_argument("--max-amount", type=Decimal, default=Decimal("10000.00"))
    parser.add_argument(
        "--entry-mode",
        choices=("mixed", "credit-only", "debit-only", "cancel-pairs"),
        default="mixed",
    )
    parser.add_argument("--dual-entry-ratio", type=Decimal, default=ZERO)
    parser.add_argument("--zero-delta-ratio", type=Decimal, default=ZERO)
    parser.add_argument(
        "--account-distribution",
        choices=("uniform", "pareto", "hotspot"),
        default="uniform",
    )
    parser.add_argument("--hot-account-ratio", type=Decimal, default=Decimal("0.90"))
    parser.add_argument("--pareto-head-count", type=int, default=10)
    parser.add_argument("--pareto-head-ratio", type=Decimal, default=Decimal("0.80"))
    parser.add_argument(
        "--order",
        choices=("interleaved", "by-account", "by-date"),
        default="interleaved",
    )
    parser.add_argument("--trap-amount-ratio", type=Decimal, default=ZERO)
    return parser


def main() -> None:
    arguments = build_parser().parse_args()
    generate(
        GeneratorConfig(
            output_dir=cast(Path, arguments.output_dir),
            rows=cast(int, arguments.rows),
            accounts=cast(int, arguments.accounts),
            dates=cast(int, arguments.dates),
            seed=cast(int, arguments.seed),
            start_date=cast(date, arguments.start_date),
            currencies=cast(tuple[str, ...], arguments.currencies),
            min_amount=cast(Decimal, arguments.min_amount),
            max_amount=cast(Decimal, arguments.max_amount),
            entry_mode=cast(EntryMode, arguments.entry_mode),
            dual_entry_ratio=cast(Decimal, arguments.dual_entry_ratio),
            zero_delta_ratio=cast(Decimal, arguments.zero_delta_ratio),
            account_distribution=cast(AccountDistribution, arguments.account_distribution),
            hot_account_ratio=cast(Decimal, arguments.hot_account_ratio),
            pareto_head_count=cast(int, arguments.pareto_head_count),
            pareto_head_ratio=cast(Decimal, arguments.pareto_head_ratio),
            order=cast(RowOrder, arguments.order),
            trap_amount_ratio=cast(Decimal, arguments.trap_amount_ratio),
        )
    )


if __name__ == "__main__":
    main()
