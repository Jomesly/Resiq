from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update

from app.maintenance import drain_cleanup, enqueue_cleanup
from app.models import LineItem, Receipt
from app.runtime import Runtime
from app.schemas import MONEY_FIELDS, TEXT_FIELDS
from app.worker.pipeline import ProcessingResult


@dataclass(frozen=True)
class Claim:
    id: UUID
    workspace_id: UUID
    original_key: str
    lease_token: UUID
    attempts: int


class JobQueue:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def claim(self) -> Claim | None:
        settings = self.runtime.settings
        with self.runtime.db.session() as session, session.begin():
            now = session.scalar(select(func.clock_timestamp()))
            session.execute(
                update(Receipt)
                .where(
                    Receipt.status == "processing",
                    Receipt.lease_expires_at < now,
                    Receipt.attempts >= settings.max_attempts,
                )
                .values(
                    status="failed",
                    lease_token=None,
                    lease_expires_at=None,
                    error="Reading timed out repeatedly. Try a clearer photo or enter this receipt by hand.",
                )
            )
            row = session.scalar(
                select(Receipt)
                .where(
                    Receipt.attempts < settings.max_attempts,
                    or_(
                        and_(Receipt.status == "queued", Receipt.available_at <= now),
                        and_(Receipt.status == "processing", Receipt.lease_expires_at < now),
                    ),
                )
                .order_by(Receipt.created_at, Receipt.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            row.status = "processing"
            row.attempts += 1
            row.lease_token = uuid4()
            row.lease_expires_at = now + timedelta(seconds=settings.lease_s)
            row.error = None
            return Claim(row.id, row.workspace_id, row.original_key, row.lease_token, row.attempts)

    def fail(self, claim: Claim, message: str, *, permanent=False) -> bool:
        with self.runtime.db.session() as session, session.begin():
            now = session.scalar(select(func.clock_timestamp()))
            result = session.execute(
                update(Receipt)
                .where(
                    Receipt.id == claim.id,
                    Receipt.status == "processing",
                    Receipt.lease_token == claim.lease_token,
                )
                .values(
                    status="failed"
                    if permanent or claim.attempts >= self.runtime.settings.max_attempts
                    else "queued",
                    error=message[:500],
                    lease_token=None,
                    lease_expires_at=None,
                    available_at=now + timedelta(seconds=min(60, 2**claim.attempts)),
                )
            )
            return result.rowcount == 1

    def complete(self, claim: Claim, result: ProcessingResult) -> bool:
        # Publish under the same row lock used by delete/reprocess. Attempt-specific
        # blobs cannot overwrite another attempt, even after a timeout or crash.
        prefix = f"{claim.workspace_id}/{claim.id}/attempts/{claim.lease_token}"
        try:
            with self.runtime.db.session() as session, session.begin():
                row = session.scalar(
                    select(Receipt).where(Receipt.id == claim.id).with_for_update()
                )
                now = session.scalar(select(func.clock_timestamp()))
                if (
                    row is None
                    or row.status != "processing"
                    or row.lease_token != claim.lease_token
                    or row.lease_expires_at < now
                ):
                    return False
                keys = {}
                if row.processed_key and "/attempts/" in row.processed_key:
                    enqueue_cleanup(session, row.processed_key.rsplit("/", 1)[0])
                for variant, data in result.images.items():
                    key = f"{prefix}/{variant}.jpg"
                    self.runtime.store.put(key, data)
                    keys[variant] = key
                row.processed_key = keys.pop("processed")
                row.stage_keys = {"original": row.stage_keys["original"], **keys}
                row.image_width, row.image_height = result.width, result.height
                row.quality = result.quality.model_dump(mode="json")
                row.ocr = [line.model_dump(mode="json") for line in result.lines]
                row.extraction = result.extraction.model_dump(mode="json")
                for field in (*TEXT_FIELDS, *MONEY_FIELDS):
                    value = getattr(result.extraction, field).value
                    if value is not None and field in MONEY_FIELDS:
                        value = Decimal(value)
                    elif value is not None and field == "receipt_date":
                        value = date.fromisoformat(value)
                    setattr(row, field, value)
                row.line_items = [
                    LineItem(
                        position=i,
                        description=item.description,
                        quantity=Decimal(item.quantity) if item.quantity else None,
                        unit_price=Decimal(item.unit_price) if item.unit_price else None,
                        amount=Decimal(item.amount),
                    )
                    for i, item in enumerate(result.extraction.line_items)
                ]
                row.status = (
                    "needs_review" if result.lines or result.extraction.total.value else "failed"
                )
                row.error = (
                    None
                    if row.status == "needs_review"
                    else "No readable text was found. Try a clearer photo or enter the receipt by hand."
                )
                row.lease_token = row.lease_expires_at = None
                row.processed_at = now
            drain_cleanup(self.runtime)
            return True
        except Exception:
            # Crash/failed writes are collected by the age-gated orphan sweep.
            raise
