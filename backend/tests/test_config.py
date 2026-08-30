import pytest
from ledger_balance.config import Settings
from pydantic import ValidationError


def test_rejects_inverted_pool_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(database_pool_min_size=11, database_pool_max_size=10)


def test_parses_comma_separated_origins() -> None:
    settings = Settings(api_allowed_origins="http://localhost:5173, http://localhost:4173")

    assert settings.allowed_origins == (
        "http://localhost:5173",
        "http://localhost:4173",
    )
