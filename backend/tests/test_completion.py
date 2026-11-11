from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models import Receipt
from app.schemas import Extraction, FieldValue, QualityReport
from app.worker.pipeline import ProcessingResult
from app.worker.queue import JobQueue


def result():
    return ProcessingResult(
        {"processed": b"photo"},
        400,
        600,
        QualityReport(blur_score=100, is_blurry=False, brightness=200, is_dark=False),
        [],
        Extraction(
            engine_version="test",
            merchant=FieldValue(value="SHOP"),
            total=FieldValue(value="12.30"),
        ),
    )


def test_completion_fences_stale_attempt_and_delete(runtime, uploaded, client, auth):
    queue = JobQueue(runtime)
    old = queue.claim()
    with runtime.db.session() as session:
        session.get(Receipt, UUID(uploaded)).lease_expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        session.commit()
    new = queue.claim()
    assert not queue.complete(old, result())
    assert queue.complete(new, result())
    detail = client.get(f"/api/receipts/{uploaded}", headers=auth).json()
    assert detail["status"] == "needs_review" and detail["total"] == "12.30"
    assert detail["image"]["width"] == 400
    assert client.post(f"/api/receipts/{uploaded}/reprocess", headers=auth).status_code == 202
    pending = queue.claim()
    assert client.delete(f"/api/receipts/{uploaded}", headers=auth).status_code == 204
    assert not queue.complete(pending, result())
    assert not runtime.store.path(f"{pending.workspace_id}/{pending.id}").exists()
