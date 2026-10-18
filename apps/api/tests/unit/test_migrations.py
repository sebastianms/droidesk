from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
TABLES = {"users", "categories", "sla_policies", "tickets", "ticket_events"}


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'migrated.db'}"


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(toml_file=PYPROJECT)
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_upgrade_creates_the_five_tables(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    assert table_names(database_url) == TABLES


def test_migrated_schema_matches_the_models(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)


def test_downgrade_removes_every_table(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    assert table_names(database_url) == set()
