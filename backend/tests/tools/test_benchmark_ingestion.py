from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, cast

import pytest
from ledger_balance.config import Settings
from ledger_balance.db.pool import Database
from ledger_balance.domain.models import AccountBalance, AccountId, RateBook
from ledger_balance.domain.reference import ReferenceResult
from ledger_balance.ingestion.service import IngestionResult
from ledger_balance.tools import benchmark_ingestion as benchmark

BALANCE = AccountBalance(AccountId(100), "acct100", Decimal("12.500000000000000000"))
REFERENCE = ReferenceResult((BALANCE,), 2, Decimal("12.500000000000000000"))


class FakeConnection:
    async def fetch(self, query: str) -> list[dict[str, object]]:
        del query
        return [
            {
                "account_id": int(BALANCE.account_id),
                "name": BALANCE.name,
                "balance_usd": BALANCE.balance_usd,
            }
        ]


class FakeDatabase:
    instances: ClassVar[list["FakeDatabase"]] = []

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connected = False
        self.disconnected = False
        self.maximum_active_connections = 0
        self.__class__.instances.append(self)

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[FakeConnection]:
        yield FakeConnection()

    async def fetch_value(self, query: str, *args: object) -> object:
        del query, args
        return "17.6"


@pytest.fixture(autouse=True)
def reset_fake_database() -> None:
    FakeDatabase.instances = []


def settings(pool_maximum: int = 10) -> Settings:
    return Settings(
        database_pool_min_size=1,
        database_pool_max_size=pool_maximum,
        ingest_concurrency=min(10, pool_maximum),
    )


def result() -> IngestionResult:
    return IngestionResult(2, 1, 1, Decimal("12.500000000000000000"))


def benchmark_result(**changes: object) -> benchmark.BenchmarkResult:
    values: dict[str, object] = {
        "concurrency": 2,
        "transaction_count": 2,
        "account_count": 1,
        "rate_count": 1,
        "total_usd": Decimal("12.500000000000000000"),
        "elapsed_seconds": 0.5,
        "rows_per_second": 4.0,
        "pool_maximum": 10,
        "queue_capacity": 2,
        "maximum_observed_connections": 2,
        "postgresql_version": "17.6",
    }
    values.update(changes)
    return benchmark.BenchmarkResult(**values)  # type: ignore[arg-type]


def test_argument_requirements_and_default_concurrency() -> None:
    parser = benchmark._parser()
    with pytest.raises(SystemExit) as missing:
        parser.parse_args([])
    assert missing.value.code == 2

    arguments = parser.parse_args(["--transactions", "transactions.csv", "--rates", "rates.csv"])
    assert arguments.concurrency == [1, 2, 5, 10]


@pytest.mark.parametrize("values", [[1, 1], [0], [11]])
async def test_invalid_concurrency_fails_before_oracle_or_connection(
    monkeypatch: pytest.MonkeyPatch, values: list[int]
) -> None:
    oracle_started = False

    def load_rates(_: Path) -> RateBook:
        nonlocal oracle_started
        oracle_started = True
        return cast(RateBook, object())

    monkeypatch.setattr(benchmark, "load_rates", load_rates)
    monkeypatch.setattr(benchmark, "Database", FakeDatabase)

    with pytest.raises(ValueError):
        await benchmark.run_benchmarks(
            Path("transactions.csv"),
            Path("rates.csv"),
            values,
            settings=settings(),
        )

    assert not oracle_started
    assert FakeDatabase.instances == []


async def test_cases_use_requested_order_fresh_databases_and_deterministic_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    times = iter([10.0, 12.0, 20.0, 24.0])

    monkeypatch.setattr(benchmark, "Database", FakeDatabase)
    monkeypatch.setattr(benchmark, "load_rates", lambda _: cast(RateBook, object()))
    monkeypatch.setattr(benchmark, "iter_transactions", lambda *_: iter(()))

    def reduce(*_: object) -> ReferenceResult:
        events.append("oracle")
        return REFERENCE

    async def ingest(
        database: FakeDatabase,
        transactions_path: Path,
        rates_path: Path,
        *,
        concurrency: int,
    ) -> IngestionResult:
        del transactions_path, rates_path
        events.append(("ingest", concurrency))
        database.maximum_active_connections = concurrency
        return result()

    monkeypatch.setattr(benchmark, "reduce_transactions", reduce)
    monkeypatch.setattr(benchmark, "ingest", ingest)
    monkeypatch.setattr(
        "ledger_balance.tools.benchmark_ingestion.time.perf_counter", lambda: next(times)
    )

    results = await benchmark.run_benchmarks(
        Path("transactions.csv"), Path("rates.csv"), [5, 2], settings=settings()
    )

    assert events == ["oracle", ("ingest", 5), ("ingest", 2)]
    assert [item.concurrency for item in results] == [5, 2]
    assert [item.elapsed_seconds for item in results] == [2.0, 4.0]
    assert [item.rows_per_second for item in results] == [1.0, 0.5]
    assert [item.maximum_observed_connections for item in results] == [5, 2]
    assert len(FakeDatabase.instances) == 2
    assert all(database.connected and database.disconnected for database in FakeDatabase.instances)


async def test_full_row_mismatch_disconnects_and_returns_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ingest(*args: object, **kwargs: object) -> IngestionResult:
        del args, kwargs
        return result()

    async def wrong_rows(_: Database) -> tuple[AccountBalance, ...]:
        return (AccountBalance(AccountId(100), "wrong", BALANCE.balance_usd),)

    monkeypatch.setattr(benchmark, "Database", FakeDatabase)
    monkeypatch.setattr(benchmark, "ingest", ingest)
    monkeypatch.setattr(benchmark, "_stored_balances", wrong_rows)
    monkeypatch.setattr("ledger_balance.tools.benchmark_ingestion.time.perf_counter", lambda: 1.0)

    with pytest.raises(RuntimeError, match="complete account rows differ"):
        await benchmark.benchmark_case(
            settings(), Path("transactions.csv"), Path("rates.csv"), 2, REFERENCE
        )

    assert FakeDatabase.instances[0].disconnected


async def test_total_mismatch_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ingest(*args: object, **kwargs: object) -> IngestionResult:
        del args, kwargs
        return IngestionResult(2, 1, 1, Decimal("99"))

    monkeypatch.setattr(benchmark, "Database", FakeDatabase)
    monkeypatch.setattr(benchmark, "ingest", ingest)
    monkeypatch.setattr("ledger_balance.tools.benchmark_ingestion.time.perf_counter", lambda: 1.0)

    with pytest.raises(RuntimeError, match="exact total differs"):
        await benchmark.benchmark_case(
            settings(), Path("transactions.csv"), Path("rates.csv"), 2, REFERENCE
        )

    assert FakeDatabase.instances[0].disconnected


def test_markdown_output_is_stable_and_uses_fixed_point(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "ledger_balance.tools.benchmark_ingestion.platform.python_version",
        lambda: "3.12.test",
    )
    monkeypatch.setattr(
        "ledger_balance.tools.benchmark_ingestion.platform.platform",
        lambda: "test-platform",
    )
    monkeypatch.setattr(benchmark, "version", lambda _: "0.30.test")

    benchmark.print_report(
        Path("transactions.csv"),
        Path("rates.csv"),
        [benchmark_result(total_usd=Decimal("12.5000"))],
    )

    output = capsys.readouterr().out
    assert "Python: 3.12.test" in output
    assert "asyncpg: 0.30.test" in output
    assert "PostgreSQL: 17.6" in output
    assert "| Workers | Transactions | Accounts | Rates | Total USD |" in output
    assert "| 2 | 2 | 1 | 1 | 12.5000 | 0.500 | 4.0 | 10 | 2 | 2 |" in output
