import secrets

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from ledger_balance.api.errors import UnauthorizedError
from ledger_balance.config import Settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    request: Request,
    presented_key: str | None = Security(api_key_header),
) -> None:
    settings: Settings = request.app.state.settings
    configured_key = settings.api_key
    if configured_key is None:
        return
    if presented_key is None or not secrets.compare_digest(
        presented_key,
        configured_key.get_secret_value(),
    ):
        raise UnauthorizedError()
