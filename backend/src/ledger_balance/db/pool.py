from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg  # type: ignore[import-untyped]
from asyncpg.pool import PoolConnectionProxy  # type: ignore[import-untyped]

from ledger_balance.config import Settings


class Database:
    """Own a bounded asyncpg pool for one application process."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None
        self._active_connections = 0
        self._maximum_active_connections = 0

    async def connect(self) -> None:
        if self._pool is not None:
            return
        pool = await asyncpg.create_pool(
            dsn=self._settings.database_url,
            min_size=self._settings.database_pool_min_size,
            max_size=self._settings.database_pool_max_size,
        )
        self._pool = pool
        self._active_connections = 0
        self._maximum_active_connections = 0

    async def disconnect(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[PoolConnectionProxy, None]:
        if self._pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self._pool.acquire() as connection:
            self._active_connections += 1
            self._maximum_active_connections = max(
                self._maximum_active_connections,
                self._active_connections,
            )
            try:
                yield connection
            finally:
                self._active_connections -= 1

    @property
    def active_connections(self) -> int:
        return self._active_connections

    @property
    def maximum_active_connections(self) -> int:
        return self._maximum_active_connections

    async def fetch_value(self, query: str, *args: object) -> Any:
        async with self.connection() as connection:
            return await connection.fetchval(query, *args)

    async def ping(self) -> bool:
        return await self.fetch_value("SELECT TRUE") is True
