from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import func, select

from app.maintenance import run_once
from app.models import WorkerHeartbeat
from app.operations import status


def test_monitor_detects_worker_and_storage_outages(runtime):
    with runtime.db.session() as session, session.begin():
        session.add(
            WorkerHeartbeat(
                id="worker-test",
                engine="fake",
                last_seen=session.scalar(select(func.clock_timestamp())),
            )
        )
    run_once(runtime)
    assert status(runtime)["ok"]
    with patch.object(runtime.store, "put", side_effect=OSError("disk failure")):
        assert "storage_unavailable" in status(runtime)["problems"]
    with runtime.db.session() as session, session.begin():
        session.get(WorkerHeartbeat, "worker-test").last_seen = session.scalar(
            select(func.clock_timestamp())
        ) - timedelta(hours=1)
    assert "no_ready_worker" in status(runtime)["problems"]


def test_maintenance_is_not_counted_as_an_ocr_worker(client, runtime):
    run_once(runtime)
    assert client.get("/readyz").status_code == 503
