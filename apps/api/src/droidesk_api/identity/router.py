from typing import Final

from fastapi import APIRouter

from droidesk_api.core.db import SessionDep
from droidesk_api.core.http_errors import ErrorBody, error_responses
from droidesk_api.core.security import TokenServiceDep
from droidesk_api.identity import schemas, service
from droidesk_api.identity.authorization import CurrentUser

BEARER: Final = "bearer"

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/auth/users")
def list_demo_users(session: SessionDep) -> list[schemas.DemoUser]:
    """Usuarios precargados de la demo, solicitantes primero. Solo alimenta la ayuda del ingreso."""
    return [
        schemas.DemoUser.model_validate(user)
        for user in service.list_demo_users(session)
    ]


@router.post(
    "/auth/login",
    responses={401: {"model": ErrorBody, "description": "El usuario no existe."}},
)
def login(
    body: schemas.LoginRequest, session: SessionDep, tokens: TokenServiceDep
) -> schemas.LoginResponse:
    """Ingreso simulado: cualquier contraseña sirve, pero el usuario debe existir.

    Nunca crea usuarios: entra con el perfil que el usuario ya tiene.
    """
    user = schemas.User.model_validate(service.authenticate(session, body.username))
    token = tokens.issue(user.id)
    return schemas.LoginResponse(
        access_token=token.value,
        token_type=BEARER,
        expires_at=token.expires_at,
        user=user,
    )


@router.get("/me", responses=error_responses(401))
def read_me(user: CurrentUser) -> schemas.User:
    return schemas.User.model_validate(user)
