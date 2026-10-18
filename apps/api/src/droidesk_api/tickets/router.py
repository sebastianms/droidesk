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
    return service.apply_transition(user, ticket_id, body.action)
