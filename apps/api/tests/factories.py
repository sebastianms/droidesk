from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session

from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.tickets.models import Ticket

REQUESTER_ID = 1
OTHER_REQUESTER_ID = 2
AGENT_ID = 5
OTHER_AGENT_ID = 6
REQUESTER_USERNAME = "ana.rojas"
AGENT_USERNAME = "elena.vidal"
ANY_PASSWORD = "cualquier-clave"
CREATED_AT = datetime(2026, 10, 19, 13, 5, tzinfo=UTC)  # lunes 10:05 en Santiago


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
