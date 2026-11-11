"""Retry durable deletions and remove old unreferenced image objects."""

import argparse
import logging
import signal
import time
from datetime import timedelta
from threading import Event
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.db import Database
from app.models import BlobCleanup, Receipt, WorkerHeartbeat
from app.runtime import Runtime
from app.services.budgets import admission_lock
from app.storage import ImageSigner, get_store

logger = logging.getLogger("resiq.maintenance")


def enqueue_cleanup(session, prefix: str):
    session.execute(insert(BlobCleanup).values(prefix=prefix).on_conflict_do_nothing())


def drain_cleanup(runtime: Runtime, limit=100) -> int:
    removed = 0
    for _ in range(limit):
        with runtime.db.session() as session, session.begin():
            row = session.scalar(
                select(BlobCleanup)
                .order_by(BlobCleanup.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                break
            try:
                runtime.store.delete_prefix(row.prefix)
            except Exception as exc:
                logger.error("cleanup_failed error_type=%s", type(exc).__name__)
                break  # Preserve the outbox record; retry on the next sweep.
            session.delete(row)
            removed += 1
    return removed


def sweep_orphans(runtime: Runtime) -> int:
    removed = 0
    with runtime.db.session() as session:
        cutoff = session.scalar(select(func.clock_timestamp())) - timedelta(
            seconds=runtime.settings.cleanup_grace_s
        )
    for key, modified in runtime.store.objects():
        if modified >= cutoff:
            continue
        parts = key.split("/")
        if len(parts) == 3 and parts[0] == ".health" and parts[2] == "probe":
            try:
                UUID(parts[1])
            except ValueError:
                continue
            runtime.store.delete(key)
            removed += 1
            continue
        try:
            workspace_id, receipt_id = UUID(parts[0]), UUID(parts[1])
        except (ValueError, IndexError):
            continue  # Never delete unrelated objects in a shared bucket.
        with runtime.db.session() as session, session.begin():
            admission_lock(session)  # Wait for uploads before checking existence.
            row = session.scalar(select(Receipt).where(Receipt.id == receipt_id).with_for_update())
            if row is not None:
                if row.workspace_id != workspace_id:
                    continue
                live = {row.original_key, row.processed_key, *row.stage_keys.values()}
                active_prefix = f"{workspace_id}/{receipt_id}/attempts/{row.lease_token}/"
                if key in live or (row.lease_token and key.startswith(active_prefix)):
                    continue
            runtime.store.delete(key)
            removed += 1
    return removed


def run_once(runtime: Runtime, *, sweep=True):
    deleted = drain_cleanup(runtime)
    orphans = sweep_orphans(runtime) if sweep else 0
    with runtime.db.session() as session, session.begin():
        session.execute(
            insert(WorkerHeartbeat)
            .values(id="maintenance", engine="maintenance", last_seen=func.clock_timestamp())
            .on_conflict_do_update(
                index_elements=["id"], set_={"last_seen": func.clock_timestamp()}
            )
        )
    logger.info("maintenance_complete deleted_prefixes=%d orphan_objects=%d", deleted, orphans)
    return deleted, orphans


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    runtime = Runtime(
        settings, Database(settings.database_url), get_store(settings), ImageSigner(settings)
    )
    last_sweep = 0.0
    stopping = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    try:
        while not stopping.is_set():
            try:
                sweep = time.monotonic() - last_sweep > 3600
                run_once(runtime, sweep=sweep or args.once)
                if sweep:
                    last_sweep = time.monotonic()
            except Exception as exc:
                logger.error("maintenance_failed error_type=%s", type(exc).__name__)
                if args.once:
                    raise
            if args.once:
                break
            stopping.wait(settings.maintenance_interval_s)
    finally:
        runtime.db.dispose()


if __name__ == "__main__":
    main()
