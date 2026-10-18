from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
)

from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import USERNAME_MAX_LENGTH

USERNAME_PATTERN = rf"^[a-z0-9._-]{{1,{USERNAME_MAX_LENGTH}}}$"
PASSWORD_MAX_LENGTH = 128


def normalize_username(value: object) -> object:
    """Recorta y pasa a minúsculas; lo que no es texto sigue su camino y falla en la validación del tipo."""
    return value.strip().lower() if isinstance(value, str) else value


# El validador previo va al final: envuelve a las restricciones, que así quedan en el contrato.
Username = Annotated[
    str,
    StringConstraints(pattern=USERNAME_PATTERN),
    BeforeValidator(normalize_username),
]


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    email: str
    role: Role


class DemoUser(BaseModel):
    """Usuario precargado, para que la pantalla de ingreso muestre con quién entrar."""

    model_config = ConfigDict(from_attributes=True)

    username: str
    name: str
    role: Role


class LoginRequest(BaseModel):
    username: Username = Field(
        description="Letras minúsculas, números, punto, guion y guion bajo (1 a 50). Se recorta y se pasa a minúsculas."
    )
    password: SecretStr = Field(
        min_length=1,
        max_length=PASSWORD_MAX_LENGTH,
        description="Se ignora: el ingreso es simulado y la contraseña nunca se guarda.",
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_at: datetime
    user: User
