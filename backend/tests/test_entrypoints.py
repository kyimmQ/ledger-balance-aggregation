from unittest.mock import Mock

from ledger_balance.api import cli as api_cli
from ledger_balance.config import Settings
from ledger_balance.ingestion import cli as ingestion_cli
from pytest import CaptureFixture, MonkeyPatch


class FakeDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def ping(self) -> bool:
        return True


async def test_ingestion_entrypoint_is_separate(
    capsys: CaptureFixture[str], monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(ingestion_cli, "Database", FakeDatabase)

    await ingestion_cli.run()

    output = capsys.readouterr().out
    assert "ingestion" in output.lower()
    assert "api serving" not in output.lower()


def test_api_entrypoint_is_separate(monkeypatch: MonkeyPatch) -> None:
    uvicorn_run = Mock()
    monkeypatch.setattr("ledger_balance.api.cli.uvicorn.run", uvicorn_run)

    api_cli.main()

    uvicorn_run.assert_called_once_with(
        "ledger_balance.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
    )
