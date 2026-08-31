import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Any, cast

import pytest
from ledger_balance.config import Settings
from ledger_balance.db.pool import Database


class AcquireContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        return None


class FakePool:
    def acquire(self) -> AbstractAsyncContextManager[object]:
        return AcquireContext()

    async def close(self) -> None:
        pass


def fake_pool() -> Any:
    return cast(Any, FakePool())


async def test_metrics_track_overlap_exception_and_cancellation() -> None:
    database = Database(Settings())
    database._pool = fake_pool()

    assert database.active_connections == 0
    assert database.maximum_active_connections == 0

    async with database.connection():
        assert database.active_connections == 1
        assert database.maximum_active_connections == 1
        async with database.connection():
            assert database.active_connections == 2
            assert database.maximum_active_connections == 2
        assert database.active_connections == 1
        assert database.maximum_active_connections == 2

    assert database.active_connections == 0
    assert database.maximum_active_connections == 2

    with pytest.raises(RuntimeError, match="ordinary failure"):
        async with database.connection():
            raise RuntimeError("ordinary failure")
    assert database.active_connections == 0

    entered = asyncio.Event()
    blocker = asyncio.Event()

    async def hold_connection() -> None:
        async with database.connection():
            entered.set()
            await blocker.wait()

    task = asyncio.create_task(hold_connection())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert database.active_connections == 0
    assert database.maximum_active_connections == 2


async def test_successful_reconnect_resets_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    pools = [fake_pool(), fake_pool()]

    async def create_pool(**kwargs: object) -> Any:
        del kwargs
        return pools.pop(0)

    monkeypatch.setattr("ledger_balance.db.pool.asyncpg.create_pool", create_pool)
    database = Database(Settings())

    await database.connect()
    async with database.connection():
        pass
    assert database.maximum_active_connections == 1
    await database.disconnect()

    await database.connect()
    assert database.active_connections == 0
    assert database.maximum_active_connections == 0
    await database.disconnect()
