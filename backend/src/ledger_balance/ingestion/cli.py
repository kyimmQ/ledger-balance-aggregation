import asyncio

from ledger_balance.config import get_settings
from ledger_balance.db.pool import Database


async def run() -> None:
    database = Database(get_settings())
    await database.connect()
    try:
        if not await database.ping():
            raise RuntimeError("PostgreSQL readiness check failed")
        print("PostgreSQL is ready; ledger ingestion is implemented in a later phase.")
    finally:
        await database.disconnect()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
