import io
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, text

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.models import Base

URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://resiq:resiq-local-only@127.0.0.1:54329/resiq"
)


@pytest.fixture
def runtime(tmp_path):
    schema = "resiq_test_" + uuid.uuid4().hex
    admin = create_engine(URL, connect_args={"connect_timeout": 5})
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    settings = Settings(
        database_url=URL,
        signing_secret="test-" + "x" * 48,
        environment="test",
        storage_root=tmp_path,
        ocr_engine="fake",
        rate_limit_enabled=False,
    )
    db = Database(URL, schema=schema)
    Base.metadata.create_all(db.engine)
    app = create_app(settings, database=db)
    yield app.state.runtime
    db.dispose()
    with admin.begin() as connection:
        connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    admin.dispose()


@pytest.fixture
def client(runtime):
    with TestClient(
        create_app(runtime.settings, database=runtime.db, store=runtime.store)
    ) as client:
        yield client


@pytest.fixture
def auth(client):
    response = client.post("/api/workspaces")
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["token"]}


@pytest.fixture
def photo():
    return (Path(__file__).parents[2] / "frontend/public/samples/kapihan.png").read_bytes()


@pytest.fixture
def blank_photo():
    buffer = io.BytesIO()
    Image.new("RGB", (400, 700), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def uploaded(client, auth, photo):
    response = client.post(
        "/api/receipts", headers=auth, files={"file": ("receipt.png", photo, "image/png")}
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]
