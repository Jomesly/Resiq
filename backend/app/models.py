from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint("status IN ('queued','processing','needs_review','verified','failed')"),
        Index("ix_receipts_queue", "status", "available_at", "lease_expires_at"),
        Index("ix_receipts_workspace_created", "workspace_id", "created_at", "id"),
        Index("ix_receipts_workspace_month", "workspace_id", "status", "receipt_date", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    original_key: Mapped[str] = mapped_column(Text)
    processed_key: Mapped[str | None] = mapped_column(Text)
    stage_keys: Mapped[dict] = mapped_column(JSONB, default=dict)
    content_type: Mapped[str] = mapped_column(String(50))
    image_width: Mapped[int] = mapped_column(default=0)
    image_height: Mapped[int] = mapped_column(default=0)
    quality: Mapped[dict | None] = mapped_column(JSONB)
    ocr: Mapped[list | None] = mapped_column(JSONB)
    extraction: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    merchant: Mapped[str | None] = mapped_column(String(250))
    merchant_tin: Mapped[str | None] = mapped_column(String(40))
    receipt_number: Mapped[str | None] = mapped_column(String(100))
    receipt_date: Mapped[date | None]
    category: Mapped[str | None] = mapped_column(String(40))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vatable_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vat_exempt: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    line_items: Mapped[list["LineItem"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LineItem.position",
    )


class LineItem(Base):
    __tablename__ = "line_items"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(primary_key=True, index=True)
    count: Mapped[int] = mapped_column(default=1)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    engine: Mapped[str] = mapped_column(String(40))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
