import logging
import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from fastapi.responses import Response

from ledger_balance.api.rate_limit import RateLimitDecision

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


UnexpectedErrorHandler = Callable[[Request, Exception], Awaitable[Response]]


def get_request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    if _REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return str(uuid4())


def get_rate_limit_headers(request: Request) -> dict[str, str]:
    decision = getattr(request.state, "rate_limit_decision", None)
    if not isinstance(decision, RateLimitDecision):
        return {}
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if decision.retry_after_seconds is not None:
        headers["Retry-After"] = str(decision.retry_after_seconds)
    return headers


async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    unexpected_error_handler: UnexpectedErrorHandler,
) -> Response:
    request.state.request_id = get_request_id(request)
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exception:
        response = await unexpected_error_handler(request, exception)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers.update(get_rate_limit_headers(request))
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
