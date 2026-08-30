from ledger_balance.api.cli import main as serve_main
from ledger_balance.ingestion.cli import main as ingest_main
from pytest import CaptureFixture


def test_ingestion_entrypoint_is_separate(capsys: CaptureFixture[str]) -> None:
    ingest_main()

    output = capsys.readouterr().out
    assert "ingestion" in output.lower()
    assert "api serving" not in output.lower()


def test_api_entrypoint_is_separate(capsys: CaptureFixture[str]) -> None:
    serve_main()

    output = capsys.readouterr().out
    assert "api serving" in output.lower()
    assert "ingestion" not in output.lower()
