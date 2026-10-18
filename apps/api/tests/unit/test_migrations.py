from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
TABLES = {
    "users",
    "categories",
    "sla_policies",
    "tickets",
    "ticket_events",
    "comments",
}
INITIAL_TABLES = TABLES - {"comments"}


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


def test_upgrade_creates_the_six_tables(
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


def column_names(database_url: str, table: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return {column["name"] for column in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def referenced_tables(database_url: str, table: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        keys = inspect(engine).get_foreign_keys(table)
        return {key["referred_table"] for key in keys}
    finally:
        engine.dispose()


def record_old_event(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO ticket_events (ticket_id, actor_id, kind, created_at)"
                    " VALUES (1, 1, 'created', '2026-10-19 13:05:00.000000')"
                )
            )
    finally:
        engine.dispose()


def record_old_comment(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO comments (ticket_id, author_id, body, created_at)"
                    " VALUES (1, 1, 'Hola', '2026-10-19 13:05:00.000000')"
                )
            )
    finally:
        engine.dispose()


def rows(database_url: str, query: str) -> list[tuple[Any, ...]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(query))]
    finally:
        engine.dispose()


def test_the_initial_schema_has_no_comments(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "0001")
    assert table_names(database_url) == INITIAL_TABLES


def test_events_link_to_their_comment(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    assert {"comment_id"} <= column_names(database_url, "ticket_events")
    assert "comments" in referenced_tables(database_url, "ticket_events")


def test_events_recorded_before_comments_existed_survive_the_upgrade(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "0001")
    record_old_event(database_url)
    command.upgrade(alembic_config, "head")
    assert rows(database_url, "SELECT kind, comment_id FROM ticket_events") == [
        ("created", None)
    ]


def test_downgrading_removes_the_comments_table(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0001")
    assert table_names(database_url) == INITIAL_TABLES


def test_downgrading_removes_the_link_from_the_events(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0001")
    assert "comment_id" not in column_names(database_url, "ticket_events")


def test_downgrading_keeps_the_events(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    record_old_event(database_url)
    command.downgrade(alembic_config, "0001")
    assert rows(database_url, "SELECT kind FROM ticket_events") == [("created",)]


def test_comments_link_to_the_comment_they_reply_to(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    assert {"reply_to_id"} <= column_names(database_url, "comments")
    assert "comments" in referenced_tables(database_url, "comments")


def test_comments_recorded_before_replies_existed_survive_the_upgrade(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "0002")
    record_old_comment(database_url)
    command.upgrade(alembic_config, "head")
    assert rows(database_url, "SELECT body, reply_to_id FROM comments") == [
        ("Hola", None)
    ]


def test_downgrading_removes_the_reply_link(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0002")
    assert "reply_to_id" not in column_names(database_url, "comments")


def test_downgrading_keeps_the_comments(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    record_old_comment(database_url)
    command.downgrade(alembic_config, "0002")
    assert rows(database_url, "SELECT body FROM comments") == [("Hola",)]
