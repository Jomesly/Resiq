import os
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select
from test_completion import result

from app.maintenance import drain_cleanup, sweep_orphans
from app.models import BlobCleanup, Receipt
from app.worker.queue import JobQueue


def test_delete_survives_storage_failure_and_retries(client, auth, uploaded, runtime):
    detail = client.get(f"/api/receipts/{uploaded}", headers=auth).json()
    with patch.object(runtime.store, "delete_prefix", side_effect=OSError("storage unavailable")):
        assert client.delete(f"/api/receipts/{uploaded}", headers=auth).status_code == 204
    assert client.get(detail["image"]["original_url"]).status_code == 404
    with runtime.db.session() as session:
        assert session.scalar(select(BlobCleanup)) is not None
    assert drain_cleanup(runtime) == 1
    assert list(runtime.store.objects()) == []


def test_reprocess_cleans_superseded_attempt_only(client, auth, uploaded, runtime):
    queue = JobQueue(runtime)
    first = queue.claim()
    assert queue.complete(first, result())
    old_prefix = f"{first.workspace_id}/{first.id}/attempts/{first.lease_token}"
    assert client.post(f"/api/receipts/{uploaded}/reprocess", headers=auth).status_code == 202
    second = queue.claim()
    assert queue.complete(second, result())
    assert not runtime.store.path(old_prefix).exists()
    assert (
        client.get(
            client.get(f"/api/receipts/{uploaded}", headers=auth).json()["image"]["processed_url"]
        ).status_code
        == 200
    )


def test_orphan_sweep_preserves_referenced_recent_and_active_files(uploaded, runtime):
    claim = JobQueue(runtime).claim()
    root = f"{claim.workspace_id}/{claim.id}"
    abandoned = f"{root}/attempts/{uuid4()}/processed.jpg"
    active = f"{root}/attempts/{claim.lease_token}/processed.jpg"
    recent = f"{root}/attempts/{uuid4()}/processed.jpg"
    with runtime.db.session() as session:
        original = session.get(Receipt, UUID(uploaded)).original_key
    for key in (abandoned, active, recent):
        runtime.store.put(key, b"image")
    for key in (abandoned, active, original):
        os.utime(runtime.store.path(key), (1, 1))
    assert sweep_orphans(runtime) == 1
    assert not runtime.store.path(abandoned).exists()
    for key in (active, recent, original):
        assert runtime.store.path(key).exists()


def test_sweep_removes_crash_leftovers_but_not_unrelated_bucket_objects(runtime):
    abandoned = f"{uuid4()}/{uuid4()}/original.jpg"
    probe = f".health/{uuid4()}/probe"
    unrelated = "another-app/photo.jpg"
    for key in (abandoned, probe, unrelated):
        runtime.store.put(key, b"image")
        os.utime(runtime.store.path(key), (1, 1))
    assert sweep_orphans(runtime) == 2
    assert runtime.store.path(unrelated).exists()
