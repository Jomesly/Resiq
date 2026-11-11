import hashlib
import hmac
import secrets
import time
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.models import RateBucket, Workspace
from app.runtime import Runtime


def check_rate(runtime: Runtime, namespace: str, identity: str, limit: int) -> None:
    if not runtime.settings.rate_limit_enabled:
        return
    hashed = hmac.new(
        runtime.settings.signing_secret.get_secret_value().encode(),
        identity.encode(),
        hashlib.sha256,
    ).hexdigest()
    key, window = f"{namespace}:{hashed}", int(time.time()) // 60
    with runtime.db.session() as session:
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
    token = secrets.token_urlsafe(32)
    with runtime.db.session() as session:
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
