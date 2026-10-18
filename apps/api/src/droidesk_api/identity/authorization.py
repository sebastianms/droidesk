from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from droidesk_api.core.db import SessionDep
from droidesk_api.core.errors import (
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
)
from droidesk_api.core.security import TokenServiceDep
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.tickets.models import Ticket

bearer_scheme = HTTPBearer(
    auto_error=False, description="Token emitido por `POST /api/v1/auth/login`."
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
    tokens: TokenServiceDep,
) -> User:
    if credentials is None:
        raise NotAuthenticatedError
    user = session.get(User, tokens.read_user_id(credentials.credentials))
    if user is None:
        raise NotAuthenticatedError
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_requester(user: CurrentUser) -> User:
    if user.role != Role.REQUESTER:
        raise ForbiddenError("Esta operación es solo para solicitantes.")
    return user


def require_agent(user: CurrentUser) -> User:
    if user.role != Role.AGENT:
        raise ForbiddenError("Esta operación es solo para agentes.")
    return user


RequesterUser = Annotated[User, Depends(require_requester)]
AgentUser = Annotated[User, Depends(require_agent)]


def ensure_can_view(user: User, ticket: Ticket) -> None:
    """Un solicitante solo ve sus tickets; uno ajeno responde como si no existiera."""
    if user.role == Role.REQUESTER and ticket.requester_id != user.id:
        raise NotFoundError("El ticket no existe.")
