from fastapi.testclient import TestClient
from ledger_balance.api.app import create_app
from ledger_balance.config import Settings


class FakeDatabase:
    def __init__(self, ready: bool = True) -> None:
        self.ready = ready
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def ping(self) -> bool:
        return self.ready


def test_liveness_and_lifecycle() -> None:
    database = FakeDatabase()
    with TestClient(create_app(Settings(), database)) as client:
        assert database.connected
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert not database.connected


def test_readiness() -> None:
    with TestClient(create_app(Settings(), FakeDatabase())) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_failure() -> None:
    with TestClient(create_app(Settings(), FakeDatabase(ready=False))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert body["error"]["message"] == "Database unavailable"
    assert response.headers["X-Request-ID"] == body["error"]["requestId"]
