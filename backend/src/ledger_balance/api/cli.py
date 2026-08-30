import uvicorn

from ledger_balance.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "ledger_balance.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
