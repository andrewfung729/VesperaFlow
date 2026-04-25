"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from vesperaflow_store import create_engine, create_session_factory
from vesperaflow_store.errors import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    StoreError,
)

from .routes.tasks import router as tasks_router
from .schemas.tasks import ErrorEnvelope
from .settings import get_settings
from .temporal_scheduler import TemporalScheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    scheduler = TemporalScheduler(settings)
    await scheduler.connect()
    app.state.scheduler = scheduler
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="VesperaFlow API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(tasks_router, prefix="/api/v1")
    app.add_exception_handler(StoreError, store_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(RuntimeError, runtime_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    return app


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error={"code": code, "message": message, "details": {}}
        ).model_dump(),
    )


async def store_error_handler(_: Request, exc: Exception) -> JSONResponse:
    status_code = 500
    code = "internal_error"
    if isinstance(exc, NotFoundError):
        status_code = 404
        code = exc.code
    elif isinstance(exc, ConflictError):
        status_code = 409
        code = exc.code
    elif isinstance(exc, InvalidStateTransitionError):
        status_code = 409
        code = exc.code
    elif isinstance(exc, StoreError):
        code = exc.code
    return _error_response(status_code, code, str(exc))


async def value_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return _error_response(422, "validation_error", str(exc))


async def runtime_error_handler(_: Request, exc: Exception) -> JSONResponse:
    message = str(exc)
    if message.startswith("execution_unavailable:"):
        return _error_response(409, "execution_unavailable", message)
    if message.startswith("unsupported_operation:"):
        return _error_response(409, "unsupported_operation", message)
    return _error_response(500, "internal_error", message)


async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorEnvelope(
            error={
                "code": "validation_error",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            }
        ).model_dump(),
    )
