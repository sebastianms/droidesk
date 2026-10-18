from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text
from sqlmodel import Field, SQLModel

from droidesk_api.core.db import text_enum
from droidesk_api.tickets.enums import Priority, TicketStatus

CATEGORY_NAME_MAX_LENGTH = 60
TITLE_MAX_LENGTH = 120
DESCRIPTION_MAX_LENGTH = 5000
COMMENT_MAX_LENGTH = 2000


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=CATEGORY_NAME_MAX_LENGTH, unique=True)


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_sla_due_at", "status", "sla_due_at"),
        Index("ix_tickets_requester_id_created_at", "requester_id", "created_at"),
        CheckConstraint(
            "sla_paused_minutes >= 0", name="sla_paused_minutes_non_negative"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=TITLE_MAX_LENGTH)
    description: str = Field(sa_type=Text, max_length=DESCRIPTION_MAX_LENGTH)
    status: TicketStatus = Field(
        default=TicketStatus.OPEN, sa_type=text_enum(TicketStatus)
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        sa_type=text_enum(Priority),
        foreign_key="sla_policies.priority",
    )
    category_id: int = Field(foreign_key="categories.id")
    requester_id: int = Field(foreign_key="users.id")
    assignee_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime
    updated_at: datetime
    sla_due_at: datetime
    sla_paused_minutes: int = 0
    on_hold_since: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_at: datetime | None = None


class Comment(SQLModel, table=True):
    """Un mensaje en el ticket; como el historial, no se edita ni se borra."""

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_ticket_id_created_at", "ticket_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="tickets.id")
    author_id: int = Field(foreign_key="users.id")
    body: str = Field(sa_type=Text, max_length=COMMENT_MAX_LENGTH)
    created_at: datetime
    reply_to_id: int | None = Field(default=None, foreign_key="comments.id")
