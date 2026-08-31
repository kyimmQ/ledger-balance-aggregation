from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ledger_balance.api.errors import ApiRouteError, DatabaseUnavailableError
from ledger_balance.api.exception_handlers import (
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from ledger_balance.api.http_context import request_context
from ledger_balance.api.rate_limit import FixedWindowRateLimiter
from ledger_balance.api.repository import BalanceReadRepository
from ledger_balance.api.routes import router
from ledger_balance.config import Settings, get_settings
from ledger_balance.db.pool import Database


class DatabaseLifecycle(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def ping(self) -> bool: ...


def create_app(
    settings: Settings | None = None,
    database: DatabaseLifecycle | None = None,
    repository: BalanceReadRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_database = database or Database(resolved_settings)
    resolved_repository = repository or BalanceReadRepository(
        cast(Database, resolved_database), resolved_settings.api_query_timeout_seconds
    )
    resolved_rate_limiter = FixedWindowRateLimiter(
        resolved_settings.api_rate_limit_requests,
        resolved_settings.api_rate_limit_window_seconds,
        resolved_settings.api_rate_limit_max_clients,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.settings = resolved_settings
        app.state.rate_limiter = resolved_rate_limiter
        await resolved_database.connect()
        app.state.database = resolved_database
        app.state.read_repository = resolved_repository
        try:
            yield
        finally:
            await resolved_database.disconnect()

    app = FastAPI(
        title="Ledger Balance Aggregation API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_exception_handler(ApiRouteError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-API-Key", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        return await request_context(request, call_next, unexpected_error_handler)

    @app.get("/health/live", response_model=dict[str, str])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", response_model=dict[str, str])
    async def ready(request: Request) -> dict[str, str]:
        database_service: DatabaseLifecycle = request.app.state.database
        try:
            ready_state = await database_service.ping()
        except Exception as error:
            raise DatabaseUnavailableError() from error
        if not ready_state:
            raise DatabaseUnavailableError()
        return {"status": "ready"}

    app.include_router(router)
    return app
