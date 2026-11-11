import hashlib
import hmac
import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import RateBucket, Workspace
from app.runtime import Runtime
from app.services.budgets import admission_lock, workspace_budget


def check_rate(runtime: Runtime, namespace: str, identity: str, limit: int) -> None:
    if not runtime.settings.rate_limit_enabled:
        return
    hashed = hmac.new(
        runtime.settings.signing_secret.get_secret_value().encode(),
        identity.encode(),
        hashlib.sha256,
    ).hexdigest()
    key = f"{namespace}:{hashed}"
    with runtime.db.session() as session:
        window = int(session.scalar(select(func.extract("epoch", func.clock_timestamp())))) // 60
        session.execute(delete(RateBucket).where(RateBucket.window < window - 2))
        statement = insert(RateBucket).values(key=key, window=window, count=1)
        statement = statement.on_conflict_do_update(
            index_elements=[RateBucket.key, RateBucket.window],
            set_={"count": RateBucket.count + 1},
            where=RateBucket.count < limit,
        ).returning(RateBucket.count)
        allowed = session.scalar(statement)
        session.commit()
    if allowed is None:
        raise HTTPException(
            429, "Too many requests. Try again in a minute.", headers={"Retry-After": "60"}
        )


def create_workspace(runtime: Runtime, client_ip: str) -> str:
    check_rate(runtime, "workspaces", client_ip, 10)
    check_rate(runtime, "workspace-global", "all", runtime.settings.workspace_creations_per_minute)
    token = secrets.token_urlsafe(32)
    with runtime.db.session() as session:
        admission_lock(session)
        workspace_budget(session, runtime.settings)
        session.add(Workspace(token_hash=hashlib.sha256(token.encode()).hexdigest()))
        session.commit()
    return token


def authenticate(runtime: Runtime, authorization: str | None) -> UUID:
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 200:
        raise HTTPException(
            401, "A valid workspace token is required.", headers={"WWW-Authenticate": "Bearer"}
        )
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    with runtime.db.session() as session:
        workspace_id = session.scalar(select(Workspace.id).where(Workspace.token_hash == digest))
    if workspace_id is None:
        raise HTTPException(
            401, "This workspace token is not valid.", headers={"WWW-Authenticate": "Bearer"}
        )
    return workspace_id


def recovery_hash(code: str) -> str:
    return hashlib.sha256(("resiq-recovery:" + code).encode()).hexdigest()


def prepare_recovery(runtime: Runtime, workspace_id: UUID) -> str:
    check_rate(runtime, "recovery-setup", str(workspace_id), 5)
    code = secrets.token_urlsafe(32)
    with runtime.db.session() as session, session.begin():
        row = session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        # Keep the active code valid until the user confirms they saved the replacement.
        row.pending_recovery_hash = recovery_hash(code)
    return code


def confirm_recovery(runtime: Runtime, workspace_id: UUID, code: str) -> None:
    check_rate(runtime, "recovery-confirm", str(workspace_id), 10)
    with runtime.db.session() as session, session.begin():
        row = session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        digest = recovery_hash(code)
        if row.recovery_hash and hmac.compare_digest(row.recovery_hash, digest):
            return  # A retry after a lost response is safe.
        if not row.pending_recovery_hash or not hmac.compare_digest(
            row.pending_recovery_hash, digest
        ):
            raise HTTPException(
                400, "This recovery code is not the pending code. Generate a new one."
            )
        row.recovery_hash, row.pending_recovery_hash = digest, None


def recover_workspace(runtime: Runtime, code: str, client_ip: str) -> str:
    check_rate(runtime, "recovery", client_ip, 10)
    check_rate(runtime, "recovery-global", "all", 100)
    with runtime.db.session() as session, session.begin():
        row = session.scalar(
            select(Workspace)
            .where(Workspace.recovery_hash == recovery_hash(code))
            .with_for_update()
        )
        if row is None:
            raise HTTPException(401, "This recovery code is not valid.")
        token = secrets.token_urlsafe(32)
        row.token_hash = hashlib.sha256(token.encode()).hexdigest()
        # Recovery also invalidates any unconfirmed replacement from an old browser.
        row.pending_recovery_hash = None
    return token


def rotate_token(runtime: Runtime, workspace_id: UUID) -> str:
    check_rate(runtime, "rotate", str(workspace_id), 5)
    with runtime.db.session() as session, session.begin():
        row = session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if not row.recovery_hash:
            raise HTTPException(409, "Save a recovery code before rotating access.")
        token = secrets.token_urlsafe(32)
        row.token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token
