from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel

import droidesk_api.models  # noqa: F401  (registra las tablas en la metadata)
from droidesk_api.core.config import get_settings
from droidesk_api.core.db import build_engine
from droidesk_api.core.errors import DomainError
from droidesk_api.core.http_errors import (
    handle_domain_error,
    handle_validation_error,
)
from droidesk_api.identity.router import router as identity_router
from droidesk_api.sla.router import router as sla_router
from droidesk_api.tickets.router import router as tickets_router


class HealthResponse(BaseModel):
    status: Literal["ok"]


def route_name_as_operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = build_engine(get_settings().database_url)
    app.state.engine = engine
    yield
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DroiDesk API",
        version=version("droidesk-api"),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        generate_unique_id_function=route_name_as_operation_id,
    )
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.include_router(identity_router)
    app.include_router(sla_router)
    app.include_router(tickets_router)

    @app.get("/api/health")
    def read_health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app
