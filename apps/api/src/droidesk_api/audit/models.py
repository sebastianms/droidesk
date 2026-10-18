from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from droidesk_api.audit.enums import EventKind
from droidesk_api.core.db import text_enum
from droidesk_api.identity.models import NAME_MAX_LENGTH

VALUE_MAX_LENGTH = NAME_MAX_LENGTH  # el evento `assigned` guarda el nombre del agente


class TicketEvent(SQLModel, table=True):
    __tablename__ = "ticket_events"
    __table_args__ = (
        Index("ix_ticket_events_ticket_id_created_at", "ticket_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="tickets.id")
    actor_id: int = Field(foreign_key="users.id")
    kind: EventKind = Field(sa_type=text_enum(EventKind))
    from_value: str | None = Field(default=None, max_length=VALUE_MAX_LENGTH)
    to_value: str | None = Field(default=None, max_length=VALUE_MAX_LENGTH)
    comment_id: int | None = Field(default=None, foreign_key="comments.id")
    created_at: datetime
