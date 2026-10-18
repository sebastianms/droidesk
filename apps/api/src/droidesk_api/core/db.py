from collections.abc import Iterator
from enum import StrEnum
from sqlite3 import Connection
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import Engine, Enum, create_engine, event
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import Session, SQLModel

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
ENUM_COLUMN_LENGTH = 20

# Debe fijarse antes de que se defina cualquier tabla: todos los modelos importan este módulo.
SQLModel.metadata.naming_convention = NAMING_CONVENTION


def text_enum(enum_class: type[StrEnum]) -> Enum:
    """Guarda el valor del enum (en minúscula) como texto, sin tipos nativos de la base."""
    return Enum(
        enum_class,
        native_enum=False,
        length=ENUM_COLUMN_LENGTH,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


def _enable_sqlite_pragmas(
    connection: Connection, _record: ConnectionPoolEntry
) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def build_engine(url: str) -> Engine:
    """Engine de la app: los pragmas viven solo aquí porque las FK activas rompen las migraciones batch."""
    is_sqlite = url.startswith("sqlite")
    connect_args: dict[str, Any] = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(url, connect_args=connect_args)
    if is_sqlite:
        event.listen(engine, "connect", _enable_sqlite_pragmas)
    return engine


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
