import pytest
from ledger_balance.config import Settings
from pydantic import ValidationError


def test_rejects_inverted_pool_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(database_pool_min_size=11, database_pool_max_size=10)


def test_accepts_ingestion_concurrency_below_pool_maximum() -> None:
    settings = Settings(database_pool_max_size=10, ingest_concurrency=5)

    assert settings.ingest_concurrency == 5


def test_accepts_ingestion_concurrency_equal_to_pool_maximum() -> None:
    settings = Settings(database_pool_max_size=10, ingest_concurrency=10)

    assert settings.ingest_concurrency == 10


def test_rejects_ingestion_concurrency_above_pool_maximum() -> None:
    with pytest.raises(
        ValidationError,
        match="INGEST_CONCURRENCY cannot exceed DATABASE_POOL_MAX_SIZE",
    ):
        Settings(database_pool_max_size=10, ingest_concurrency=11)


def test_has_no_database_batch_size_setting() -> None:
    assert "ingest_batch_size" not in Settings.model_fields


def test_parses_comma_separated_origins() -> None:
    settings = Settings(api_allowed_origins="http://localhost:5173, http://localhost:4173")

    assert settings.allowed_origins == (
        "http://localhost:5173",
        "http://localhost:4173",
    )


def test_rejects_invalid_api_query_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(api_query_timeout_seconds=0)


@pytest.mark.parametrize(
    "field",
    [
        "api_rate_limit_requests",
        "api_rate_limit_window_seconds",
        "api_rate_limit_max_clients",
    ],
)
def test_rejects_non_positive_rate_limit_settings(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: 0})
