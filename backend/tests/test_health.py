from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health():
    with TestClient(create_app(Settings())) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
