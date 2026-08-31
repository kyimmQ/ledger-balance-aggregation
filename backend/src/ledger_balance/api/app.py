import logging
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol, cast
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ledger_balance.api.contracts import ErrorDetail, ErrorResponse
from ledger_balance.api.errors import ApiRouteError, DatabaseUnavailableError
from ledger_balance.api.repository import BalanceReadRepository
from ledger_balance.api.routes import router
from ledger_balance.config import Settings, get_settings
from ledger_balance.db.pool import Database

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class DatabaseLifecycle(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def ping(self) -> bool: ...


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if _REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return str(uuid4())


def _error_response(request: Request, error: ApiRouteError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    body = ErrorResponse(
        error=ErrorDetail(code=error.code, message=error.public_message, requestId=request_id)
    )
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(by_alias=True),
        headers={"X-Request-ID": request_id},
    )


async def _api_error_handler(request: Request, exception: Exception) -> JSONResponse:
    route_error = cast(ApiRouteError, exception)
    logger.warning(
        "api_error",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "error_code": route_error.code,
            "status_code": route_error.status_code,
        },
    )
    return _error_response(request, route_error)


async def _validation_error_handler(request: Request, exception: Exception) -> JSONResponse:
    del exception
    return _error_response(request, ApiRouteError(400, "INVALID_REQUEST", "Invalid request"))


async def _http_error_handler(request: Request, exception: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exception)
    if http_error.status_code == status.HTTP_404_NOT_FOUND:
        error = ApiRouteError(404, "NOT_FOUND", "Route not found")
    elif http_error.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        error = ApiRouteError(405, "METHOD_NOT_ALLOWED", "Method not allowed")
    else:
        error = ApiRouteError(500, "INTERNAL_ERROR", "Internal server error")
    return _error_response(request, error)


async def _unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
    logger.exception(
        "api_internal_error",
        extra={"request_id": getattr(request.state, "request_id", "")},
        exc_info=exception,
    )
    return _error_response(request, ApiRouteError(500, "INTERNAL_ERROR", "Internal server error"))


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    app.add_exception_handler(ApiRouteError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = _request_id(request)
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as exception:
            response = await _unexpected_error_handler(request, exception)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/") or request.url.path.startswith("/health/"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            "api_request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
            },
        )
        return response

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
