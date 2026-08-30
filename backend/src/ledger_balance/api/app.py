from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ledger_balance.config import Settings, get_settings
from ledger_balance.db.pool import Database


class DatabaseLifecycle(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def ping(self) -> bool: ...


class HealthResponse(BaseModel):
    status: str


def create_app(
    settings: Settings | None = None,
    database: DatabaseLifecycle | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_database = database or Database(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await resolved_database.connect()
        app.state.database = resolved_database
        try:
            yield
        finally:
            await resolved_database.disconnect()

    app = FastAPI(
        title="Ledger Balance Aggregation API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/health/ready", response_model=HealthResponse)
    async def ready(request: Request) -> HealthResponse:
        database_service: DatabaseLifecycle = request.app.state.database
        if not await database_service.ping():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            )
        return HealthResponse(status="ready")

    return app
