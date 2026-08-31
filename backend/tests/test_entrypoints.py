from unittest.mock import Mock

from ledger_balance.api import cli as api_cli
from pytest import MonkeyPatch


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
