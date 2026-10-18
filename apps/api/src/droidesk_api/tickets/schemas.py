from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from droidesk_api.audit.enums import EventKind
from droidesk_api.sla.status import SlaState
from droidesk_api.tickets.enums import Priority, TicketStatus
from droidesk_api.tickets.lifecycle import TicketAction
from droidesk_api.tickets.models import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH

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


class Event(BaseModel):
    """Una entrada del historial; `from_value` y `to_value` son estados, prioridades o el nombre del agente asignado."""

    id: int
    kind: EventKind
    actor: UserRef
    from_value: str | None
    to_value: str | None
    created_at: datetime


class TicketDetail(TicketSummary):
    description: str
    resolved_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    allowed_actions: list[TicketAction]
    history: list[Event]


class TicketCreate(BaseModel):
    title: Title
    description: Description
    category_id: int
    priority: Priority = Priority.MEDIUM


class TransitionRequest(BaseModel):
    action: StateAction
