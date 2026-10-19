import secrets
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel

import droidesk_api.models  # noqa: F401  (registra las tablas en la metadata)
from droidesk_api.core.clock import get_clock
from droidesk_api.core.config import AppMode, Settings, get_settings
from droidesk_api.core.db import build_engine, get_session
from droidesk_api.main import create_app
from droidesk_api.seed import seed_base_data
from tests.factories import ANY_PASSWORD
from tests.fakes import FakeClock

MONDAY_MORNING = datetime(2026, 10, 19, 13, 5, tzinfo=UTC)  # 10:05 en Santiago


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        jwt_secret=SecretStr(secrets.token_hex(32)),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        mode=AppMode.EMPTY,
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(MONDAY_MORNING)


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    test_engine = build_engine(settings.database_url)
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as test_session:
        yield test_session


@pytest.fixture
def demo_data(session: Session) -> None:
    seed_base_data(session)


@pytest.fixture
def app(settings: Settings, engine: Engine, clock: FakeClock) -> FastAPI:
    def session_for_request() -> Iterator[Session]:
        with Session(engine) as request_session:
            yield request_session

    test_app = create_app()
    test_app.dependency_overrides[get_settings] = lambda: settings
    test_app.dependency_overrides[get_session] = session_for_request
    test_app.dependency_overrides[get_clock] = lambda: clock
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def login_as(client: TestClient, demo_data: None) -> Callable[[str], dict[str, str]]:
    def login(username: str) -> dict[str, str]:
        credentials = {"username": username, "password": ANY_PASSWORD}
        response = client.post("/api/v1/auth/login", json=credentials)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return login


@pytest.fixture(autouse=True)
def fresh_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
