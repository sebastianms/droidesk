from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from droidesk_api.audit.enums import EventKind
from droidesk_api.core.ids import Id
from droidesk_api.sla.status import SlaState
from droidesk_api.tickets.enums import Priority, TicketStatus
from droidesk_api.tickets.lifecycle import TicketAction
from droidesk_api.tickets.models import (
    COMMENT_MAX_LENGTH,
    DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
)

# Los largos se validan después de recortar los espacios: un texto de solo espacios queda vacío.
Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH),
]
Description = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH
    ),
]
CommentBody = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=COMMENT_MAX_LENGTH
    ),
]
# Las acciones que cambian el estado; comentar y cambiar la prioridad tienen sus propios endpoints.
StateAction = Literal[
    TicketAction.TAKE,
    TicketAction.CANCEL,
    TicketAction.HOLD,
    TicketAction.RESUME,
    TicketAction.RESOLVE,
    TicketAction.CLOSE,
    TicketAction.REOPEN,
]


class TicketView(StrEnum):
    MINE = "mine"
    QUEUE = "queue"
    ASSIGNED = "assigned"


class Category(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class Sla(BaseModel):
    """Estado del SLA; `due_at` es nulo mientras está en pausa y en los tickets cancelados."""

    state: SlaState | None
    due_at: datetime | None


class TicketSummary(BaseModel):
    id: int
    title: str
    status: TicketStatus
    priority: Priority
    category: Category
    requester: UserRef
    assignee: UserRef | None
    created_at: datetime
    sla: Sla
    comment_count: int


class Event(BaseModel):
    """Una entrada del historial; `from_value` y `to_value` son estados, prioridades o el nombre del agente asignado."""

    id: int
    kind: EventKind
    actor: UserRef
    from_value: str | None
    to_value: str | None
    created_at: datetime


class Comment(BaseModel):
    """Texto plano: quien lo muestre no debe interpretarlo como HTML."""

    id: int
    author: UserRef
    body: str
    created_at: datetime
    reply_to_id: int | None


class TicketDetail(TicketSummary):
    description: str
    resolved_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    allowed_actions: list[TicketAction]
    history: list[Event]
    comments: list[Comment]


class TicketCreate(BaseModel):
    title: Title
    description: Description
    category_id: Id
    priority: Priority = Priority.MEDIUM


class TicketUpdate(BaseModel):
    priority: Priority


class TransitionRequest(BaseModel):
    action: StateAction


class CommentCreate(BaseModel):
    body: CommentBody
    reply_to_id: Id | None = None
