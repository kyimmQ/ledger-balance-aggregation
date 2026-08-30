from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Validated process configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "postgresql://ledger:ledger@localhost:5432/ledger"
    database_pool_min_size: int = Field(default=2, ge=1)
    database_pool_max_size: int = Field(default=10, ge=1)
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65_535)
    api_allowed_origins: str = "http://localhost:5173"
    ingest_concurrency: int = Field(default=10, ge=1, le=100)
    ingest_batch_size: int = Field(default=250, ge=1, le=10_000)

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(
            origin.strip() for origin in self.api_allowed_origins.split(",") if origin.strip()
        )

    @model_validator(mode="after")
    def validate_pool_bounds(self) -> "Settings":
        if self.database_pool_min_size > self.database_pool_max_size:
            raise ValueError("DATABASE_POOL_MIN_SIZE cannot exceed DATABASE_POOL_MAX_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
