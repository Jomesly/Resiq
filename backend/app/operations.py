"""Private operational checks. No receipt text, tokens, or user identifiers are returned."""

import json
import shutil
import sys
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.config import Settings
from app.db import Database
from app.models import BlobCleanup, Receipt, WorkerHeartbeat
from app.runtime import Runtime
from app.storage import ImageSigner, get_store


def status(runtime: Runtime):
    settings = runtime.settings
    with runtime.db.session() as session:
        now = session.scalar(select(func.clock_timestamp()))
        counts = dict(
            session.execute(select(Receipt.status, func.count()).group_by(Receipt.status)).all()
        )
        oldest = session.scalar(
            select(func.min(Receipt.available_at)).where(Receipt.status == "queued")
        )
        workers = session.scalar(
            select(func.count())
            .select_from(WorkerHeartbeat)
            .where(
                WorkerHeartbeat.engine != "maintenance",
                WorkerHeartbeat.last_seen > now - timedelta(seconds=settings.lease_s),
            )
        )
        maintenance = session.get(WorkerHeartbeat, "maintenance")
        cleanup = session.scalar(select(func.count()).select_from(BlobCleanup))
        cleanup_oldest = session.scalar(select(func.min(BlobCleanup.created_at)))
    problems = []
    if not workers:
        problems.append("no_ready_worker")
    if oldest and (now - oldest).total_seconds() > 600:
        problems.append("queue_wait_over_10_minutes")
    if cleanup_oldest and (now - cleanup_oldest).total_seconds() > 3600:
        problems.append("cleanup_overdue")
    if (
        not maintenance
        or (now - maintenance.last_seen).total_seconds() > settings.maintenance_interval_s * 3
    ):
        problems.append("maintenance_stale")
    prefix = f".health/{uuid4()}"
    try:
        runtime.store.put(prefix + "/probe", b"resiq")
        if runtime.store.get(prefix + "/probe") != b"resiq":
            raise OSError("Probe mismatch")
    except Exception:
        problems.append("storage_unavailable")
    finally:
        try:
            runtime.store.delete_prefix(prefix)
        except Exception:
            if "storage_unavailable" not in problems:
                problems.append("storage_unavailable")
    disk_free = None
    if settings.storage_backend == "local":
        disk_free = shutil.disk_usage(settings.storage_root).free
        if disk_free < 1024**3:
            problems.append("storage_under_1GiB_free")
    return {
        "ok": not problems,
        "problems": problems,
        "receipts_by_status": counts,
        "ready_workers": workers,
        "cleanup_pending": cleanup,
        "storage_free_bytes": disk_free,
    }


def main():
    settings = Settings()
    db = Database(settings.database_url)
    try:
        report = status(Runtime(settings, db, get_store(settings), ImageSigner(settings)))
        print(json.dumps(report))
        return 0 if report["ok"] else 1
    except Exception as exc:
        print(json.dumps({"ok": False, "problems": [type(exc).__name__]}))
        return 1
    finally:
        db.dispose()


if __name__ == "__main__":
    sys.exit(main())
