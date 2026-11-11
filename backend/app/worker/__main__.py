import logging
import signal
import time
from uuid import uuid4

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.db import Database
from app.models import WorkerHeartbeat
from app.runtime import Runtime
from app.storage import ImageSigner, get_store
from app.worker.queue import JobQueue
from app.worker.supervisor import OcrSupervisor

logger = logging.getLogger("resiq.worker")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    runtime = Runtime(
        settings, Database(settings.database_url), get_store(settings), ImageSigner(settings)
    )
    queue = JobQueue(runtime)
    worker_id = uuid4().hex
    stopping = False
    supervisor = None

    def stop(*_):
        nonlocal stopping
        stopping = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    try:
        while not stopping:
            try:
                if supervisor is None:
                    supervisor = OcrSupervisor(settings)
                    supervisor.ready()
                    logger.info("engine_ready worker=%s engine=%s", worker_id, settings.ocr_engine)
                with runtime.db.session() as session, session.begin():
                    session.execute(
                        insert(WorkerHeartbeat)
                        .values(
                            id=worker_id,
                            engine=settings.ocr_engine,
                            last_seen=func.clock_timestamp(),
                        )
                        .on_conflict_do_update(
                            index_elements=["id"], set_={"last_seen": func.clock_timestamp()}
                        )
                    )
                claim = queue.claim()
                if claim is None:
                    time.sleep(settings.worker_poll_s)
                    continue
                start = time.monotonic()
                try:
                    result = supervisor.run(runtime.store.get(claim.original_key))
                    published = queue.complete(claim, result)
                    logger.info(
                        "job_finished receipt=%s attempt=%s published=%s duration_ms=%d",
                        claim.id,
                        claim.attempts,
                        published,
                        (time.monotonic() - start) * 1000,
                    )
                except Exception as exc:
                    logger.error(
                        "job_failed receipt=%s attempt=%s error_type=%s",
                        claim.id,
                        claim.attempts,
                        type(exc).__name__,
                    )
                    queue.fail(
                        claim,
                        "Reading could not finish. We will retry; you can enter the receipt by hand if retries fail.",
                        permanent=isinstance(exc, FileNotFoundError),
                    )
                    supervisor.close()
                    supervisor = None
            except Exception as exc:
                logger.error("worker_recovering error_type=%s", type(exc).__name__)
                if supervisor:
                    supervisor.close()
                    supervisor = None
                time.sleep(5)
    finally:
        if supervisor:
            supervisor.close()
        with runtime.db.session() as session, session.begin():
            session.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.id == worker_id))
        runtime.db.dispose()


if __name__ == "__main__":
    main()
