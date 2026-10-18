from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session

from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.models import Ticket

REQUESTER_ID = 1
OTHER_REQUESTER_ID = 2
AGENT_ID = 5
OTHER_AGENT_ID = 6
THIRD_AGENT_ID = 7
REQUESTER_USERNAME = "ana.rojas"
OTHER_REQUESTER_USERNAME = "bruno.castillo"
AGENT_USERNAME = "elena.vidal"
OTHER_AGENT_USERNAME = "felipe.araya"
THIRD_AGENT_USERNAME = "gabriela.soto"
ANY_PASSWORD = "cualquier-clave"
CREATED_AT = datetime(2026, 10, 19, 13, 5, tzinfo=UTC)  # lunes 10:05 en Santiago
# Lo que cada estado deja en el ticket; AGENT_ID es el agente asignado.
STATUS_FIELDS: dict[TicketStatus, dict[str, Any]] = {
    TicketStatus.OPEN: {},
    TicketStatus.IN_PROGRESS: {"assignee_id": AGENT_ID},
    TicketStatus.ON_HOLD: {"assignee_id": AGENT_ID, "on_hold_since": CREATED_AT},
    TicketStatus.RESOLVED: {"assignee_id": AGENT_ID, "resolved_at": CREATED_AT},
    TicketStatus.CLOSED: {
        "assignee_id": AGENT_ID,
        "resolved_at": CREATED_AT,
        "closed_at": CREATED_AT,
    },
    TicketStatus.CANCELLED: {"cancelled_at": CREATED_AT},
}


def make_user(user_id: int, role: Role) -> User:
    handle = f"user{user_id}"
    return User(
        id=user_id,
        username=handle,
        name=handle,
        email=f"{handle}@droidesk.local",
        role=role,
    )


def make_ticket(**overrides: Any) -> Ticket:
    fields: dict[str, Any] = {
        "title": "No puedo entrar a la VPN",
        "description": "Desde esta mañana la VPN rechaza mis credenciales.",
        "category_id": 1,
        "requester_id": REQUESTER_ID,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "sla_due_at": CREATED_AT + timedelta(days=1),
    }
    return Ticket(**(fields | overrides))


def add_ticket(session: Session, **overrides: Any) -> Ticket:
    ticket = make_ticket(**overrides)
    session.add(ticket)
    session.commit()
    return ticket


def add_ticket_in(session: Session, status: TicketStatus, **overrides: Any) -> Ticket:
    """Un ticket con los campos que su estado exige; `overrides` pisa cualquiera."""
    return add_ticket(
        session, **(STATUS_FIELDS[status] | {"status": status} | overrides)
    )
