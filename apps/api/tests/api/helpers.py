from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

from droidesk_api.core.db import persisted_id
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.models import Ticket
from tests.factories import add_ticket, add_ticket_in

LoginAs = Callable[[str], dict[str, str]]
Act = Callable[[str, int, str], Response]
Read = Callable[[str, int], Response]
PostComment = Callable[[str, int, str], Response]
PostReply = Callable[[str, int, str, int | None], Response]
TICKETS_URL = "/api/v1/tickets"
NOT_FOUND = {"code": "not_found", "message": "El ticket no existe."}
NEW_TICKET = {
    "title": "No puedo entrar a la VPN",
    "description": "Desde esta mañana la VPN rechaza mis credenciales.",
    "category_id": 4,
}


def add_ticket_id(session: Session, **overrides: Any) -> int:
    return persisted_id(add_ticket(session, **overrides))


def add_ticket_in_id(session: Session, status: TicketStatus, **overrides: Any) -> int:
    return persisted_id(add_ticket_in(session, status, **overrides))


def reload(session: Session, ticket_id: int) -> Ticket:
    """Lee el ticket tal como lo dejó la API, que usa otra sesión."""
    session.expire_all()
    return session.get_one(Ticket, ticket_id)


def transitions_url(ticket_id: int) -> str:
    return f"{TICKETS_URL}/{ticket_id}/transitions"


def comments_url(ticket_id: int) -> str:
    return f"{TICKETS_URL}/{ticket_id}/comments"


def published_operations(app: FastAPI) -> dict[str, set[str]]:
    """Métodos HTTP de cada ruta del contrato: `app.routes` no expone las de los routers incluidos."""
    return {
        path: set(operations) for path, operations in app.openapi()["paths"].items()
    }


def post_ticket(
    client: TestClient, headers: dict[str, str], **overrides: Any
) -> Response:
    return client.post(TICKETS_URL, headers=headers, json=NEW_TICKET | overrides)
