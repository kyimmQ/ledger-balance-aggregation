from decimal import Decimal
from pathlib import Path
from typing import ClassVar

import pytest
from ledger_balance.config import Settings
from ledger_balance.ingestion import cli
from ledger_balance.ingestion.service import IngestionResult
from ledger_balance.input.errors import InputFileError


class FakeDatabase:
    instances: ClassVar[list["FakeDatabase"]] = []

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.events: list[str] = []
        self.__class__.instances.append(self)

    async def connect(self) -> None:
        self.events.append("connect")

    async def disconnect(self) -> None:
        self.events.append("disconnect")


@pytest.fixture(autouse=True)
def reset_databases() -> None:
    FakeDatabase.instances = []


async def test_run_connects_ingests_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = IngestionResult(5, 2, 3, Decimal("96.407375"))

    async def ingest(database: FakeDatabase, transactions: Path, rates: Path) -> IngestionResult:
        assert database.events == ["connect"]
        assert transactions == Path("transactions.csv")
        assert rates == Path("rates.csv")
        return expected

    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setattr(cli, "ingest", ingest)

    result = await cli.run(Path("transactions.csv"), Path("rates.csv"))

    assert result == expected
    assert FakeDatabase.instances[0].events == ["connect", "disconnect"]


async def test_run_disconnects_when_ingestion_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args: object) -> IngestionResult:
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
