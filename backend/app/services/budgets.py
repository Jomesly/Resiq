"""Database-wide admission limits shared by API replicas and all workspaces."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Receipt, Workspace


def admission_lock(session: Session) -> None:
    # Always take this before workspace/receipt locks. Released on commit/rollback.
    session.execute(select(func.pg_advisory_xact_lock(782314902)))


def receipt_budget(session: Session, settings: Settings, workspace_id: UUID, *, upload: bool):
    pending = Receipt.status.in_(("queued", "processing"))
    total, waiting, own, own_waiting = session.execute(
        select(
            func.count(),
            func.count().filter(pending),
            func.count().filter(Receipt.workspace_id == workspace_id),
            func.count().filter(pending, Receipt.workspace_id == workspace_id),
        ).select_from(Receipt)
    ).one()
    if waiting >= settings.max_pending_total or own_waiting >= settings.max_pending_per_workspace:
        raise HTTPException(
            429,
            "The receipt queue is full. Wait for existing receipts to finish.",
            headers={"Retry-After": "60"},
        )
    if upload and (
        total >= settings.max_receipts_total or own >= settings.max_receipts_per_workspace
    ):
        raise HTTPException(429, "Receipt storage is full. Remove receipts before uploading more.")


def workspace_budget(session: Session, settings: Settings):
    if session.scalar(select(func.count()).select_from(Workspace)) >= settings.max_workspaces:
        raise HTTPException(
            503, "New workspaces are temporarily unavailable.", headers={"Retry-After": "3600"}
        )
