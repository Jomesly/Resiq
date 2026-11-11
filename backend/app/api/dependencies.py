from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from app.runtime import Runtime
from app.services.access import authenticate


def runtime(request: Request) -> Runtime:
    return request.app.state.runtime


RuntimeDep = Annotated[Runtime, Depends(runtime)]


def workspace(runtime: RuntimeDep, authorization: Annotated[str | None, Header()] = None) -> UUID:
    return authenticate(runtime, authorization)


WorkspaceDep = Annotated[UUID, Depends(workspace)]
