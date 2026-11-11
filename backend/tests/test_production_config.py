import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app


def production(**overrides):
    return Settings(
        _env_file=None,
        **{
            "environment": "production",
            "signing_secret": "s" * 48,
            "operations_token": "o" * 48,
            "database_url": "postgresql+psycopg://resiq:" + "d" * 32 + "@db/resiq",
            "public_api_url": "https://receipts.example.com",
            "cors_origins": ["https://receipts.example.com"],
            **overrides,
        },
    )


@pytest.mark.parametrize(
    "change",
    [
        {"signing_secret": "resiq-development-only-change-before-deploying"},
        {"database_url": "postgresql+psycopg://resiq:resiq-local-only@db/resiq"},
        {"public_api_url": "http://localhost:8000"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["https://example.com/path"]},
        {"cors_origins": []},
        {"operations_token": ""},
        {"rate_limit_enabled": False},
    ],
)
def test_production_refuses_unsafe_configuration(change):
    with pytest.raises(ValidationError):
        production(**change)


def test_api_rate_limit_applies_before_body_parsing(runtime):
    runtime.settings.rate_limit_enabled = True
    runtime.settings.requests_per_ip_per_minute = 1
    with TestClient(
        create_app(runtime.settings, database=runtime.db, store=runtime.store)
    ) as client:
        assert client.post("/api/workspaces").status_code == 201
        result = client.post("/api/receipts", content=b"not a receipt")
        assert result.status_code == 429
        assert result.headers["Retry-After"] == "60"


def test_json_body_is_bounded(client):
    assert client.post("/api/workspaces/recover", content=b"x" * 1_048_577).status_code == 413


def test_production_hides_api_docs(runtime):
    settings = production()
    with TestClient(create_app(settings, database=runtime.db, store=runtime.store)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/ops/status").status_code == 404
