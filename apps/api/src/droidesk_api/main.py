from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


def create_app() -> FastAPI:
    app = FastAPI(title="DroiDesk API", version=version("droidesk-api"))

    @app.get("/api/health")
    def read_health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app
