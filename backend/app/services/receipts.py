import base64
import hashlib
import hmac
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import BinaryIO
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.models import LineItem, Receipt, Workspace
from app.runtime import Runtime
from app.schemas import (
    MONEY_FIELDS,
    JournalEntry,
    JournalList,
    LineItemResponse,
    ReceiptDetail,
    ReceiptImage,
    ReceiptList,
    ReceiptSummary,
    ReceiptUpdate,
    UploadResult,
)
from app.services.access import check_rate
from app.vision.io import UnsupportedImageError, jpeg, load_image


def money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def month_bounds(month: str) -> tuple[date, date]:
    try:
        if len(month) != 7 or month[4] != "-":
            raise ValueError
        year, number = map(int, month.split("-"))
        start = date(year, number, 1)
        end = date(year + 1, 1, 1) if number == 12 else date(year, number + 1, 1)
        return start, end
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, "Use a month in YYYY-MM format.") from exc


def receipt_summary(runtime: Runtime, row: Receipt) -> ReceiptSummary:
    variant = "processed" if row.processed_key else "original"
    return ReceiptSummary(
        id=row.id,
        status=row.status,
        merchant=row.merchant,
        receipt_number=row.receipt_number,
        receipt_date=row.receipt_date,
        total=money(row.total),
        category=row.category,
        thumbnail_url=runtime.signer.url(row.id, variant),
        created_at=row.created_at,
        error=row.error,
    )


def journal_entry(runtime: Runtime, row: Receipt) -> JournalEntry:
    return JournalEntry(
        **receipt_summary(runtime, row).model_dump(),
        merchant_tin=row.merchant_tin,
        **{field: money(getattr(row, field)) for field in MONEY_FIELDS if field != "total"},
    )


def receipt_detail(runtime: Runtime, row: Receipt) -> ReceiptDetail:
    original = runtime.signer.url(row.id, "original")
    processed = runtime.signer.url(row.id, "processed") if row.processed_key else original
    return ReceiptDetail(
        **journal_entry(runtime, row).model_dump(),
        line_items=[
            LineItemResponse(
                id=item.id,
                position=item.position,
                description=item.description,
                quantity=format(item.quantity, "f").rstrip("0").rstrip(".")
                if item.quantity is not None and "." in str(item.quantity)
                else str(item.quantity)
                if item.quantity is not None
                else None,
                unit_price=money(item.unit_price),
                amount=money(item.amount),
            )
            for item in row.line_items
        ],
        extraction=row.extraction,
        quality=row.quality,
        ocr_lines=row.ocr or [],
        image=ReceiptImage(
            original_url=original,
            processed_url=processed,
            width=row.image_width,
            height=row.image_height,
        ),
        stages={variant: runtime.signer.url(row.id, variant) for variant in row.stage_keys},
        verified_at=row.verified_at,
    )


class ReceiptService:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def owned(
        self, session: Session, workspace_id: UUID, receipt_id: UUID, *, lock=False
    ) -> Receipt:
        statement = (
            select(Receipt)
            .where(Receipt.id == receipt_id, Receipt.workspace_id == workspace_id)
            .options(selectinload(Receipt.line_items))
        )
        if lock:
            statement = statement.with_for_update()
        receipt = session.scalar(statement)
        if receipt is None:
            raise HTTPException(404, "This receipt could not be found.")
        return receipt

    def upload(self, workspace_id: UUID, file: BinaryIO) -> UploadResult:
        settings = self.runtime.settings
        check_rate(self.runtime, "uploads", str(workspace_id), 30)
        data = bytearray()
        while chunk := file.read(min(65536, settings.max_upload_bytes + 1)):
            data.extend(chunk)
            if len(data) > settings.max_upload_bytes:
                raise HTTPException(413, "This photo is too large: use one under 10 MB.")
        try:
            image, content_type, extension = load_image(
                bytes(data), settings.max_image_side, settings.max_image_pixels
            )
        except UnsupportedImageError as exc:
            raise HTTPException(415, str(exc)) from exc
        receipt_id = uuid4()
        prefix = f"{workspace_id}/{receipt_id}"
        original_key, preview_key = f"{prefix}/original.{extension}", f"{prefix}/preview.jpg"
        try:
            with self.runtime.db.session() as session:
                session.execute(
                    select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()
                )
                count = session.scalar(
                    select(func.count())
                    .select_from(Receipt)
                    .where(Receipt.workspace_id == workspace_id)
                )
                pending = session.scalar(
                    select(func.count())
                    .select_from(Receipt)
                    .where(
                        Receipt.workspace_id == workspace_id,
                        Receipt.status.in_(["queued", "processing"]),
                    )
                )
                if (
                    count >= settings.max_receipts_per_workspace
                    or pending >= settings.max_pending_per_workspace
                ):
                    raise HTTPException(
                        429,
                        "This workspace has reached its receipt or pending-upload limit. Finish or remove receipts before uploading more.",
                    )
                self.runtime.store.put(original_key, bytes(data))
                self.runtime.store.put(preview_key, jpeg(image))
                session.add(
                    Receipt(
                        id=receipt_id,
                        workspace_id=workspace_id,
                        original_key=original_key,
                        content_type=content_type,
                        stage_keys={"original": preview_key},
                        image_width=image.shape[1],
                        image_height=image.shape[0],
                    )
                )
                session.commit()
        except Exception:
            self.runtime.store.delete_prefix(prefix)
            raise
        return UploadResult(id=receipt_id, status="queued")

    def get(self, workspace_id: UUID, receipt_id: UUID) -> ReceiptDetail:
        with self.runtime.db.session() as session:
            return receipt_detail(self.runtime, self.owned(session, workspace_id, receipt_id))

    def cursor(self, workspace_id: UUID, row: Receipt) -> str:
        payload = json.dumps([row.created_at.isoformat(), str(row.id)], separators=(",", ":"))
        signature = hmac.new(
            self.runtime.signer.key, f"{workspace_id}:{payload}".encode(), hashlib.sha256
        ).hexdigest()
        return base64.urlsafe_b64encode(f"{signature}:{payload}".encode()).decode().rstrip("=")

    def decode_cursor(self, workspace_id: UUID, cursor: str) -> tuple[datetime, UUID]:
        try:
            if len(cursor) > 512:
                raise ValueError
            signature, payload = (
                base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split(":", 1)
            )
            expected = hmac.new(
                self.runtime.signer.key, f"{workspace_id}:{payload}".encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError
            timestamp, receipt_id = json.loads(payload)
            parsed = datetime.fromisoformat(timestamp)
            if parsed.tzinfo is None:
                raise ValueError
            return parsed, UUID(receipt_id)
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise HTTPException(400, "This receipt cursor is invalid.") from exc

    def list(
        self,
        workspace_id: UUID,
        *,
        status: str | None = None,
        month: str | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        journal=False,
    ):
        statement = select(Receipt).where(Receipt.workspace_id == workspace_id)
        if status:
            statement = statement.where(Receipt.status == status)
        if month:
            start, end = month_bounds(month)
            statement = statement.where(
                and_(Receipt.receipt_date >= start, Receipt.receipt_date < end)
                if journal
                else or_(
                    and_(Receipt.receipt_date >= start, Receipt.receipt_date < end),
                    and_(
                        Receipt.receipt_date.is_(None),
                        Receipt.created_at >= datetime.combine(start, datetime.min.time(), UTC),
                        Receipt.created_at < datetime.combine(end, datetime.min.time(), UTC),
                    ),
                )
            )
        if q:
            # Escape LIKE wildcards: a user searching for '%' means a literal percent sign.
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            statement = statement.where(
                or_(
                    Receipt.merchant.ilike(pattern, escape="\\"),
                    Receipt.receipt_number.ilike(pattern, escape="\\"),
                )
            )
        if cursor:
            timestamp, receipt_id = self.decode_cursor(workspace_id, cursor)
            statement = statement.where(
                tuple_(Receipt.created_at, Receipt.id) < tuple_(timestamp, receipt_id)
            )
        statement = statement.order_by(Receipt.created_at.desc(), Receipt.id.desc()).limit(
            limit + 1
        )
        with self.runtime.db.session() as session:
            rows = list(session.scalars(statement))
            has_more = len(rows) > limit
            rows = rows[:limit]
            next_cursor = self.cursor(workspace_id, rows[-1]) if has_more else None
            if journal:
                return JournalList(
                    items=[journal_entry(self.runtime, row) for row in rows],
                    next_cursor=next_cursor,
                )
            return ReceiptList(
                items=[receipt_summary(self.runtime, row) for row in rows], next_cursor=next_cursor
            )

    def update(self, workspace_id: UUID, receipt_id: UUID, update: ReceiptUpdate) -> ReceiptDetail:
        with self.runtime.db.session() as session:
            row = self.owned(session, workspace_id, receipt_id, lock=True)
            if row.status in ("queued", "processing"):
                raise HTTPException(409, "This receipt is still being read.")
            values = update.model_dump(exclude={"line_items"})
            for key, value in values.items():
                setattr(
                    row, key, Decimal(value) if key in MONEY_FIELDS and value is not None else value
                )
            row.line_items = [
                LineItem(
                    position=index,
                    description=item.description,
                    quantity=Decimal(item.quantity) if item.quantity is not None else None,
                    unit_price=Decimal(item.unit_price) if item.unit_price is not None else None,
                    amount=Decimal(item.amount),
                )
                for index, item in enumerate(update.line_items)
            ]
            row.status, row.verified_at, row.error = "verified", datetime.now(UTC), None
            session.commit()
            return receipt_detail(self.runtime, row)

    def reprocess(self, workspace_id: UUID, receipt_id: UUID, force: bool) -> UploadResult:
        check_rate(self.runtime, "reprocess", str(workspace_id), 20)
        with self.runtime.db.session() as session:
            row = self.owned(session, workspace_id, receipt_id, lock=True)
            if row.status in ("queued", "processing"):
                raise HTTPException(409, "This receipt is already being read.")
            if row.status == "verified" and not force:
                raise HTTPException(409, "Confirm before reading a saved receipt again.")
            row.status, row.attempts, row.error = "queued", 0, None
            row.lease_token = row.lease_expires_at = row.verified_at = None
            row.available_at = datetime.now(UTC)
            session.commit()
            return UploadResult(id=row.id, status=row.status)

    def delete(self, workspace_id: UUID, receipt_id: UUID) -> None:
        with self.runtime.db.session() as session:
            row = self.owned(session, workspace_id, receipt_id, lock=True)
            self.runtime.store.delete_prefix(f"{workspace_id}/{receipt_id}")
            session.delete(row)
            session.commit()
