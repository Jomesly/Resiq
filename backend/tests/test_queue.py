from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models import Receipt
from app.worker.queue import JobQueue


def test_concurrent_claims_are_distinct(client, auth, photo, uploaded, runtime):
    client.post("/api/receipts", headers=auth, files={"file": ("receipt.png", photo)})
    queue = JobQueue(runtime)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: queue.claim(), range(2)))
    assert all(claims)
    assert len({claim.id for claim in claims}) == 2
    assert queue.claim() is None


def test_expired_lease_is_fenced_and_attempt_limit_is_terminal(uploaded, runtime):
    queue = JobQueue(runtime)
    old = queue.claim()
    assert old.attempts == 1
    with runtime.db.session() as session:
        receipt = session.get(Receipt, UUID(uploaded))
        receipt.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    new = queue.claim()
    assert new.id == old.id and new.lease_token != old.lease_token
    assert queue.fail(old, "stale worker") is False
    assert queue.fail(new, "retry me") is True
    with runtime.db.session() as session:
        row = session.get(Receipt, UUID(uploaded))
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    third = queue.claim()
    assert third.attempts == 3
    queue.fail(third, "still broken")
    with runtime.db.session() as session:
        receipt = session.get(Receipt, UUID(uploaded))
        assert receipt.status == "failed"
        assert receipt.lease_token is None


def test_exhausted_crash_is_marked_failed(uploaded, runtime):
    with runtime.db.session() as session:
        receipt = session.get(Receipt, UUID(uploaded))
        receipt.status = "processing"
        receipt.attempts = 3
        receipt.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert JobQueue(runtime).claim() is None
    with runtime.db.session() as session:
        assert session.get(Receipt, UUID(uploaded)).status == "failed"
