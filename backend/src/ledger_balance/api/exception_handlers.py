import logging
from typing import cast
from uuid import uuid4

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ledger_balance.api.contracts import ErrorDetail, ErrorResponse
from ledger_balance.api.errors import ApiRouteError
from ledger_balance.api.http_context import get_rate_limit_headers

logger = logging.getLogger(__name__)


def error_response(request: Request, error: ApiRouteError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    body = ErrorResponse(
        error=ErrorDetail(code=error.code, message=error.public_message, requestId=request_id)
    )
    headers = {"X-Request-ID": request_id, **get_rate_limit_headers(request)}
    if error.status_code == status.HTTP_401_UNAUTHORIZED:
        headers["WWW-Authenticate"] = "ApiKey"
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(by_alias=True),
        headers=headers,
    )


async def api_error_handler(request: Request, exception: Exception) -> JSONResponse:
    route_error = cast(ApiRouteError, exception)
    logger.warning(
        "api_error",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "error_code": route_error.code,
            "status_code": route_error.status_code,
        },
    )
    return error_response(request, route_error)


async def validation_error_handler(request: Request, exception: Exception) -> JSONResponse:
    del exception
    return error_response(request, ApiRouteError(400, "INVALID_REQUEST", "Invalid request"))


async def http_error_handler(request: Request, exception: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exception)
    if http_error.status_code == status.HTTP_404_NOT_FOUND:
        error = ApiRouteError(404, "NOT_FOUND", "Route not found")
    elif http_error.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        error = ApiRouteError(405, "METHOD_NOT_ALLOWED", "Method not allowed")
    else:
        error = ApiRouteError(500, "INTERNAL_ERROR", "Internal server error")
    return error_response(request, error)


async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
    logger.exception(
        "api_internal_error",
        extra={"request_id": getattr(request.state, "request_id", "")},
        exc_info=exception,
    )
    return error_response(request, ApiRouteError(500, "INTERNAL_ERROR", "Internal server error"))
