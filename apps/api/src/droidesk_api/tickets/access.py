from droidesk_api.core.errors import NotFoundError
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.tickets.models import Ticket

TICKET_NOT_FOUND_MESSAGE = "El ticket no existe."


def ensure_can_view(user: User, ticket: Ticket) -> None:
    """Un solicitante solo ve sus tickets; uno ajeno responde como si no existiera."""
    if user.role == Role.REQUESTER and ticket.requester_id != user.id:
        raise NotFoundError(TICKET_NOT_FOUND_MESSAGE)
