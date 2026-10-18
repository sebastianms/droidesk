import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, Table, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import Session, SQLModel

from droidesk_api.core.db import ENUM_COLUMN_LENGTH, persisted_id
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.tickets.enums import Priority
from droidesk_api.tickets.models import Ticket
from tests.factories import add_ticket, make_ticket

EXPECTED_TABLE_COUNT = 5  # users, categories, sla_policies, tickets, ticket_events


def pragma(engine: Engine, name: str) -> object:
    with engine.connect() as connection:
        return connection.execute(text(f"PRAGMA {name}")).scalar_one()


def test_engine_enforces_foreign_keys(engine: Engine) -> None:
    assert pragma(engine, "foreign_keys") == 1


def test_engine_uses_wal_journal(engine: Engine) -> None:
    assert pragma(engine, "journal_mode") == "wal"


def test_orphan_rows_are_rejected(session: Session) -> None:
    session.add(make_ticket(category_id=99, requester_id=99))
    with pytest.raises(IntegrityError):
        session.commit()


def unnamed_by_convention(table: Table) -> list[str]:
    constraint_name = re.compile(rf"(pk|uq|fk|ck)_{table.name}(_\w+)?")
    index_name = re.compile(rf"ix_{table.name}(_\w+)?")
    return [
        f"{table.name}.{name}"
        for names, pattern in (
            ([c.name for c in table.constraints], constraint_name),
            ([i.name for i in table.indexes], index_name),
        )
        for name in map(str, names)
        if pattern.fullmatch(name) is None
    ]


def test_every_table_follows_the_naming_convention() -> None:
    tables = SQLModel.metadata.sorted_tables
    assert len(tables) == EXPECTED_TABLE_COUNT
    assert [name for table in tables for name in unnamed_by_convention(table)] == []


def test_enums_are_stored_as_lowercase_text(session: Session) -> None:
    session.add(
        User(
            username="ana",
            name="Ana",
            email="ana@droidesk.local",
            role=Role.REQUESTER,
        )
    )
    session.commit()
    assert (
        session.connection().execute(text("SELECT role FROM users")).scalar_one()
        == "requester"
    )


def test_enum_columns_leave_room_for_new_values() -> None:
    longest = max(len(member.value) for member in Priority)
    assert longest < ENUM_COLUMN_LENGTH


@pytest.mark.usefixtures("demo_data")
def test_naive_datetimes_are_rejected(session: Session) -> None:
    naive = datetime(2026, 10, 19, 10, 5)  # noqa: DTZ001
    session.add(make_ticket(created_at=naive))
    with pytest.raises(StatementError, match="timezone"):
        session.commit()


@pytest.mark.usefixtures("demo_data")
def test_datetimes_come_back_in_utc(session: Session) -> None:
    ticket = add_ticket(
        session, created_at=datetime.fromisoformat("2026-10-19T10:05:00-03:00")
    )
    session.expire_all()
    assert session.get_one(Ticket, ticket.id).created_at == datetime(
        2026, 10, 19, 13, 5, tzinfo=UTC
    )


def test_a_saved_row_exposes_its_id(session: Session, demo_data: None) -> None:
    assert persisted_id(add_ticket(session)) == 1


def test_a_row_that_was_not_saved_has_no_id() -> None:
    with pytest.raises(ValueError, match="no se guardó"):
        persisted_id(make_ticket())
