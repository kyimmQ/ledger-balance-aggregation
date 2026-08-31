import asyncio
from collections.abc import Coroutine
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

import pytest
from ledger_balance.config import Settings
from ledger_balance.ingestion import cli
from ledger_balance.ingestion.errors import WorkItemPersistenceError
from ledger_balance.ingestion.models import IngestionResult
from ledger_balance.input.errors import InputFileError


class FakeDatabase:
    instances: ClassVar[list["FakeDatabase"]] = []
    lifecycle: ClassVar[list[str]] = []

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.events: list[str] = []
        self.__class__.instances.append(self)

    async def connect(self) -> None:
        self.events.append("connect")
        self.__class__.lifecycle.append("connect")

    async def disconnect(self) -> None:
        self.events.append("disconnect")
        self.__class__.lifecycle.append("disconnect")


@pytest.fixture(autouse=True)
def reset_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeDatabase.instances = []
    FakeDatabase.lifecycle = []
    settings = Settings(
        database_pool_min_size=1,
        database_pool_max_size=7,
        ingest_concurrency=4,
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)


async def test_run_connects_ingests_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = IngestionResult(5, 2, 3, Decimal("96.407375"))

    async def ingest(
        database: FakeDatabase,
        transactions: Path,
        rates: Path,
        *,
        concurrency: int,
    ) -> IngestionResult:
        assert database.events == ["connect"]
        assert transactions == Path("transactions.csv")
        assert rates == Path("rates.csv")
        assert concurrency == 4
        return expected

    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setattr(cli, "ingest", ingest)

    result = await cli.run(Path("transactions.csv"), Path("rates.csv"))

    assert result == expected
    assert FakeDatabase.instances[0].events == ["connect", "disconnect"]


async def test_run_disconnects_when_ingestion_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args: object, concurrency: int) -> IngestionResult:
        assert concurrency == 4
        raise RuntimeError("verification failed")

    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setattr(cli, "ingest", fail)

    with pytest.raises(RuntimeError, match="verification failed"):
        await cli.run(Path("transactions.csv"), Path("rates.csv"))

    assert FakeDatabase.instances[0].events == ["connect", "disconnect"]


def test_main_requires_both_paths(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main([])

    assert raised.value.code == 2
    assert "--transactions" in capsys.readouterr().err


def test_main_prints_exact_success_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def succeed(_transactions: Path, _rates: Path) -> IngestionResult:
        return IngestionResult(5, 4, 5, Decimal("96.407375"))

    monkeypatch.setattr(cli, "run", succeed)

    cli.main(["--transactions", "transactions.csv", "--rates", "rates.csv"])

    captured = capsys.readouterr()
    assert captured.out == ("ingested transactions=5 accounts=4 rates=5 total_usd=96.407375\n")
    assert captured.err == ""


@pytest.mark.parametrize(
    "error",
    [
        InputFileError(Path("bad.csv"), 2, "rate", "invalid decimal"),
        OSError("file unavailable"),
        RuntimeError("database verification failed"),
    ],
)
def test_main_reports_operational_errors(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fail(_transactions: Path, _rates: Path) -> IngestionResult:
        raise error

    monkeypatch.setattr(cli, "run", fail)

    with pytest.raises(SystemExit) as raised:
        cli.main(["--transactions", "transactions.csv", "--rates", "rates.csv"])

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert captured.err == f"error: {error}\n"


async def test_run_disconnects_only_after_cancelled_ingestion_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingestion_started = asyncio.Event()
    cancellation_received = asyncio.Event()
    allow_worker_finish = asyncio.Event()

    async def controlled_ingest(
        _database: FakeDatabase,
        _transactions: Path,
        _rates: Path,
        *,
        concurrency: int,
    ) -> IngestionResult:
        assert concurrency == 4
        FakeDatabase.lifecycle.append("ingest_started")
        ingestion_started.set()
        try:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        except asyncio.CancelledError:
            FakeDatabase.lifecycle.append("worker_cancelled")
            cancellation_received.set()
            await allow_worker_finish.wait()
            raise
        finally:
            FakeDatabase.lifecycle.append("worker_finished")

    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setattr(cli, "ingest", controlled_ingest)

    run_task = asyncio.create_task(cli.run(Path("transactions.csv"), Path("rates.csv")))
    await asyncio.wait_for(ingestion_started.wait(), timeout=1)
    run_task.cancel()
    await asyncio.wait_for(cancellation_received.wait(), timeout=1)

    assert FakeDatabase.lifecycle == ["connect", "ingest_started", "worker_cancelled"]

    allow_worker_finish.set()
    async with asyncio.timeout(1):
        with pytest.raises(asyncio.CancelledError):
            await run_task

    assert FakeDatabase.lifecycle == [
        "connect",
        "ingest_started",
        "worker_cancelled",
        "worker_finished",
        "disconnect",
    ]


def test_main_reports_worker_persistence_error_without_exception_group(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fail(_transactions: Path, _rates: Path) -> IngestionResult:
        raise WorkItemPersistenceError(17, RuntimeError("connection lost"))

    monkeypatch.setattr(cli, "run", fail)

    with pytest.raises(SystemExit) as raised:
        cli.main(["--transactions", "transactions.csv", "--rates", "rates.csv"])

    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert captured.out == ""
    assert captured.err == "error: transaction 17 persistence failed: connection lost\n"


def test_main_does_not_catch_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupt(coroutine: Coroutine[object, object, IngestionResult]) -> IngestionResult:
        coroutine.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(asyncio, "run", interrupt)

    with pytest.raises(KeyboardInterrupt):
        cli.main(["--transactions", "transactions.csv", "--rates", "rates.csv"])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_does_not_catch_system_exit_from_runtime(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def exit_runtime(coroutine: Coroutine[object, object, IngestionResult]) -> IngestionResult:
        coroutine.close()
        raise SystemExit(130)

    monkeypatch.setattr(asyncio, "run", exit_runtime)

    with pytest.raises(SystemExit) as raised:
        cli.main(["--transactions", "transactions.csv", "--rates", "rates.csv"])

    captured = capsys.readouterr()
    assert raised.value.code == 130
    assert captured.out == ""
    assert captured.err == ""
