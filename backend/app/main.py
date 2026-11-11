import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.routes import router
from app.config import Settings, get_settings
from app.db import Database
from app.runtime import Runtime
from app.storage import BlobStore, ImageSigner, get_store

logger = logging.getLogger("resiq.api")


class UploadBodyLimit:
    def __init__(self, app: ASGIApp, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["path"] != "/api/receipts" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        length = dict(scope["headers"]).get(b"content-length", b"0")
        if length.isdigit() and int(length) > self.limit:
            return await JSONResponse({"detail": "This upload is too large."}, status_code=413)(
                scope, receive, send
            )
        seen = 0

        async def bounded_receive():
            nonlocal seen
            message = await receive()
            seen += len(message.get("body", b""))
            if seen > self.limit:
                raise HTTPException(413, "This upload is too large.")
            return message

        return await self.app(scope, bounded_receive, send)


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    store: BlobStore | None = None,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()
    db = database or Database(settings.database_url)
    runtime = Runtime(settings, db, store or get_store(settings), ImageSigner(settings))

    @asynccontextmanager
    async def lifespan(app):
        yield
        if database is None:
            db.dispose()

    app = FastAPI(title="Resiq API", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.add_middleware(UploadBodyLimit, limit=settings.max_upload_bytes + 1_048_576)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        start = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request id=%s method=%s route=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            request.scope.get("route").path if request.scope.get("route") else "unmatched",
            response.status_code,
            round((time.monotonic() - start) * 1000),
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        problems = [
            {"field": ".".join(str(part) for part in item["loc"][1:]), "message": item["msg"]}
            for item in error.errors()
        ]
        return JSONResponse(
            {"detail": "Check the submitted fields.", "errors": problems}, status_code=422
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        logger.error(
            "request_failed id=%s error_type=%s",
            getattr(request.state, "request_id", "unknown"),
            type(error).__name__,
        )
        return JSONResponse(
            {"detail": "The request could not be completed. Please try again."}, status_code=500
        )

    app.include_router(router)
    return app
