from fastapi import APIRouter, Depends, status
from sqlmodel import col, select

from droidesk_api.core.db import SessionDep
from droidesk_api.core.http_errors import error_responses
from droidesk_api.identity.authorization import (
    CurrentUser,
    RequesterUser,
    get_current_user,
)
from droidesk_api.tickets import schemas
from droidesk_api.tickets.dependencies import TicketServiceDep
from droidesk_api.tickets.models import Category

router = APIRouter(
    prefix="/api/v1", tags=["tickets"], dependencies=[Depends(get_current_user)]
)


@router.get("/categories", responses=error_responses(401))
def list_categories(session: SessionDep) -> list[schemas.Category]:
    categories = session.exec(select(Category).order_by(col(Category.id)))
    return [schemas.Category.model_validate(category) for category in categories]


@router.post(
    "/tickets",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403),
)
def create_ticket(
    body: schemas.TicketCreate, requester: RequesterUser, service: TicketServiceDep
) -> schemas.TicketDetail:
    return service.create_ticket(requester, body)


@router.get("/tickets", responses=error_responses(401, 403))
def list_tickets(
    user: CurrentUser,
    service: TicketServiceDep,
    view: schemas.TicketView | None = None,
) -> list[schemas.TicketSummary]:
    """Lista según el perfil.

    - Solicitante: `mine` (por defecto), sus tickets del más reciente al más antiguo.
    - Agente: `queue` (por defecto), los tickets no finales; y `assigned`, los suyos.
      Ambas van por vencimiento: primero el reloj corriendo, luego los en espera.

    Pedir una vista que no es de su perfil responde 403.
    """
    return service.list_tickets(user, view)


@router.get("/tickets/{ticket_id}", responses=error_responses(401, 404))
def read_ticket(
    ticket_id: int, user: CurrentUser, service: TicketServiceDep
) -> schemas.TicketDetail:
    return service.get_ticket_for(user, ticket_id)


@router.post(
    "/tickets/{ticket_id}/transitions", responses=error_responses(401, 403, 404, 409)
)
def transition_ticket(
    ticket_id: int,
    body: schemas.TransitionRequest,
    user: CurrentUser,
    service: TicketServiceDep,
) -> schemas.TicketDetail:
    """Aplica una acción de estado; `allowed_actions` del ticket dice cuáles ofrecer.

    403 si el perfil nunca puede hacerla; 409 `already_taken` si otro agente tomó el
    ticket primero y 409 `action_not_allowed` si el estado o la relación con el ticket
    no la permiten.
    """
    return service.apply_transition(user, ticket_id, body.action)


@router.post(
    "/tickets/{ticket_id}/comments",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 404, 409),
)
def add_comment(
    ticket_id: int,
    body: schemas.CommentCreate,
    user: CurrentUser,
    service: TicketServiceDep,
) -> schemas.TicketDetail:
    """Comenta un ticket que no está en un estado final y devuelve su detalle actualizado.

    Si el solicitante comenta un ticket En espera, este vuelve a En progreso y su plazo se
    reanuda. Un comentario del agente no cambia el estado. 409 `action_not_allowed` si el
    ticket está Cerrado o Cancelado; un ticket ajeno responde 404.
    """
    return service.add_comment(user, ticket_id, body)
