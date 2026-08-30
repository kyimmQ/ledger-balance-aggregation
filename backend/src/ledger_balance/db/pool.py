from typing import Any

import asyncpg  # type: ignore[import-untyped]

from ledger_balance.config import Settings


class Database:
    """Own a bounded asyncpg pool for one application process."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            dsn=self._settings.database_url,
            min_size=self._settings.database_pool_min_size,
            max_size=self._settings.database_pool_max_size,
        )

    async def disconnect(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None

    async def fetch_value(self, query: str, *args: object) -> Any:
        if self._pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self._pool.acquire() as connection:
            return await connection.fetchval(query, *args)

    async def ping(self) -> bool:
        return await self.fetch_value("SELECT TRUE") is True
