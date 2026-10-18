from dataclasses import dataclass

from droidesk_api.audit.models import TicketEvent
from droidesk_api.core.db import persisted_id
from droidesk_api.identity.models import User
from droidesk_api.tickets import schemas
from droidesk_api.tickets.lifecycle import TicketAction
from droidesk_api.tickets.models import Category, Ticket


@dataclass(frozen=True)
class TicketRow:
    """Un ticket junto con las filas que su vista necesita."""

    ticket: Ticket
    category: Category
    requester: User
    assignee: User | None


@dataclass(frozen=True)
class DetailFacts:
    """Lo que el servicio calcula aparte de la fila para armar el detalle."""

    sla: schemas.Sla
    allowed_actions: list[TicketAction]
    history: list[schemas.Event]


def to_summary(row: TicketRow, sla: schemas.Sla) -> schemas.TicketSummary:
    ticket = row.ticket
    return schemas.TicketSummary(
        id=persisted_id(ticket),
        title=ticket.title,
        status=ticket.status,
        priority=ticket.priority,
        category=schemas.Category.model_validate(row.category),
        requester=schemas.UserRef.model_validate(row.requester),
        assignee=_user_ref(row.assignee),
        created_at=ticket.created_at,
        sla=sla,
    )


def to_detail(row: TicketRow, facts: DetailFacts) -> schemas.TicketDetail:
    ticket = row.ticket
    return schemas.TicketDetail(
        **dict(to_summary(row, facts.sla)),
        description=ticket.description,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        cancelled_at=ticket.cancelled_at,
        allowed_actions=facts.allowed_actions,
        history=facts.history,
    )


def to_event(event: TicketEvent, actor: User) -> schemas.Event:
    return schemas.Event(
        id=persisted_id(event),
        kind=event.kind,
        actor=schemas.UserRef.model_validate(actor),
        from_value=event.from_value,
        to_value=event.to_value,
        created_at=event.created_at,
    )


def _user_ref(user: User | None) -> schemas.UserRef | None:
    return None if user is None else schemas.UserRef.model_validate(user)
