from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text

from app.api.dependencies import RuntimeDep, WorkspaceDep
from app.models import Receipt, WorkerHeartbeat
from app.schemas import (
    JournalList,
    MonthlySummary,
    ReceiptDetail,
    ReceiptList,
    ReceiptUpdate,
    Status,
    UploadResult,
    WorkspaceToken,
)
from app.services.access import create_workspace
from app.services.journal import JournalService
from app.services.receipts import ReceiptService

router = APIRouter()
Limit = Annotated[int, Query(ge=1, le=100)]
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/healthz", response_model=dict[str, str])
def health():
    return {"status": "ok"}


@router.get("/readyz", response_model=dict[str, str])
def ready(runtime: RuntimeDep):
    try:
        with runtime.db.session() as session:
            session.execute(text("SELECT 1"))
            workers = session.scalar(
                select(func.count())
                .select_from(WorkerHeartbeat)
                .where(
                    WorkerHeartbeat.last_seen
                    > datetime.now(UTC) - timedelta(seconds=runtime.settings.lease_s)
                )
            )
        if not workers:
            raise HTTPException(503, "No OCR worker is ready.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "The database is not ready.") from exc
    return {"status": "ok", "database": "ok", "worker": "ok"}


@router.post("/api/workspaces", response_model=WorkspaceToken, status_code=201)
def workspaces(request: Request, runtime: RuntimeDep):
    return WorkspaceToken(
        token=create_workspace(runtime, request.client.host if request.client else "unknown")
    )


@router.post("/api/receipts", response_model=UploadResult, status_code=202)
def upload(file: UploadFile, runtime: RuntimeDep, workspace: WorkspaceDep):
    try:
        return ReceiptService(runtime).upload(workspace, file.file)
    finally:
        file.file.close()


@router.get("/api/receipts", response_model=ReceiptList)
def receipts(
    runtime: RuntimeDep,
    workspace: WorkspaceDep,
    status: Status | None = None,
    month: Month | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Limit = 50,
):
    return ReceiptService(runtime).list(
        workspace, status=status, month=month, q=q, cursor=cursor, limit=limit
    )


@router.get("/api/receipts/export.csv")
def export(runtime: RuntimeDep, workspace: WorkspaceDep, month: Month):
    return StreamingResponse(
        JournalService(runtime).export(workspace, month),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="resiq-{month}.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/api/receipts/{receipt_id}", response_model=ReceiptDetail)
def receipt(receipt_id: UUID, runtime: RuntimeDep, workspace: WorkspaceDep):
    return ReceiptService(runtime).get(workspace, receipt_id)


@router.put("/api/receipts/{receipt_id}", response_model=ReceiptDetail)
def update(receipt_id: UUID, payload: ReceiptUpdate, runtime: RuntimeDep, workspace: WorkspaceDep):
    return ReceiptService(runtime).update(workspace, receipt_id, payload)


@router.post("/api/receipts/{receipt_id}/reprocess", response_model=UploadResult, status_code=202)
def reprocess(receipt_id: UUID, runtime: RuntimeDep, workspace: WorkspaceDep, force: bool = False):
    return ReceiptService(runtime).reprocess(workspace, receipt_id, force)


@router.delete("/api/receipts/{receipt_id}", status_code=204)
def delete(receipt_id: UUID, runtime: RuntimeDep, workspace: WorkspaceDep):
    ReceiptService(runtime).delete(workspace, receipt_id)
    return Response(status_code=204)


@router.get("/api/journal", response_model=JournalList)
def journal(
    runtime: RuntimeDep,
    workspace: WorkspaceDep,
    month: Month,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Limit = 50,
):
    return ReceiptService(runtime).list(
        workspace, status="verified", month=month, cursor=cursor, limit=limit, journal=True
    )


@router.get("/api/journal/months", response_model=list[str])
def months(runtime: RuntimeDep, workspace: WorkspaceDep):
    return JournalService(runtime).months(workspace)


@router.get("/api/stats/summary", response_model=MonthlySummary)
def stats(runtime: RuntimeDep, workspace: WorkspaceDep, month: Month):
    return JournalService(runtime).summary(workspace, month)


@router.get("/api/images/{receipt_id}/{variant}")
def image(
    receipt_id: UUID,
    variant: str,
    runtime: RuntimeDep,
    exp: int,
    sig: Annotated[str, Query(max_length=100)],
):
    if not runtime.signer.valid(receipt_id, variant, exp, sig):
        raise HTTPException(403, "This image link is invalid or expired. Reload the receipt.")
    with runtime.db.session() as session:
        row = session.get(Receipt, receipt_id)
        if row is None:
            raise HTTPException(404, "This receipt could not be found.")
        key = row.processed_key if variant == "processed" else row.stage_keys.get(variant)
        if variant == "original" and not key:
            key = row.original_key
        content_type = row.content_type if key == row.original_key else "image/jpeg"
        if not key:
            raise HTTPException(404, "This image stage is not available yet.")
        try:
            data = runtime.store.get(key)
        except FileNotFoundError as exc:
            raise HTTPException(404, "This receipt image is no longer available.") from exc
    return Response(
        data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
