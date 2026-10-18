from sqlmodel import Session, select

from droidesk_api.core.errors import NotAuthenticatedError
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User

UNKNOWN_USER_MESSAGE = (
    "El usuario no existe. Revisa los usuarios de demo en el ícono ?."
)
ROLE_ORDER = {role: position for position, role in enumerate(Role)}


def authenticate(session: Session, username: str) -> User:
    """Ingreso simulado: basta con que el usuario exista; `username` ya viene normalizado."""
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise NotAuthenticatedError(UNKNOWN_USER_MESSAGE)
    return user


def list_demo_users(session: Session) -> list[User]:
    """Solicitantes primero y, dentro de cada perfil, por nombre."""
    return sorted(
        session.exec(select(User)),
        key=lambda user: (ROLE_ORDER[user.role], user.name.casefold()),
    )
