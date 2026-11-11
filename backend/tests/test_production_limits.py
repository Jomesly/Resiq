from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import func, select

from app.models import Receipt
from app.worker.queue import JobQueue


def ready(runtime, ids):
    with runtime.db.session() as session, session.begin():
        for receipt_id in ids:
            session.get(Receipt, UUID(receipt_id)).status = "needs_review"


def test_concurrent_reprocess_cannot_exceed_pending_budget(client, auth, photo, runtime):
    ids = [
        client.post("/api/receipts", headers=auth, files={"file": ("photo.png", photo)}).json()[
            "id"
        ]
        for _ in range(3)
    ]
    ready(runtime, ids)
    runtime.settings.max_pending_per_workspace = 1
    with ThreadPoolExecutor(max_workers=3) as pool:
        statuses = list(
            pool.map(
                lambda rid: client.post(f"/api/receipts/{rid}/reprocess", headers=auth).status_code,
                ids,
            )
        )
    assert sorted(statuses) == [202, 429, 429]
    with runtime.db.session() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Receipt).where(Receipt.status == "queued")
            )
            == 1
        )


def test_new_workspace_does_not_bypass_global_queue_budget(client, auth, photo, uploaded, runtime):
    runtime.settings.max_pending_total = 1
    other = {"Authorization": "Bearer " + client.post("/api/workspaces").json()["token"]}
    assert (
        client.post("/api/receipts", headers=other, files={"file": ("p.png", photo)}).status_code
        == 429
    )
    ready(runtime, [uploaded])
    assert (
        client.post("/api/receipts", headers=other, files={"file": ("p.png", photo)}).status_code
        == 202
    )
    assert client.post(f"/api/receipts/{uploaded}/reprocess", headers=auth).status_code == 429


def test_global_storage_and_workspace_caps(client, auth, photo, uploaded, runtime):
    runtime.settings.max_receipts_total = 1
    ready(runtime, [uploaded])
    other = {"Authorization": "Bearer " + client.post("/api/workspaces").json()["token"]}
    assert (
        client.post("/api/receipts", headers=other, files={"file": ("p.png", photo)}).status_code
        == 429
    )
    runtime.settings.max_workspaces = 2
    assert client.post("/api/workspaces").status_code == 503


def test_reprocess_uses_database_clock_even_if_api_clock_is_ahead(client, auth, uploaded, runtime):
    ready(runtime, [uploaded])

    class Ahead(datetime):
        @classmethod
        def now(cls, tz=UTC):
            return datetime.now(tz) + timedelta(days=1)

    with patch("app.services.receipts.datetime", Ahead):
        assert client.post(f"/api/receipts/{uploaded}/reprocess", headers=auth).status_code == 202
    assert JobQueue(runtime).claim() is not None
