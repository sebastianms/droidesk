from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar


class ErrorCode(StrEnum):
    NOT_AUTHENTICATED = "not_authenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    ALREADY_TAKEN = "already_taken"
    ACTION_NOT_ALLOWED = "action_not_allowed"


class DomainError(Exception):
    status_code: int
    code: ErrorCode
    default_message: str
    headers: ClassVar[Mapping[str, str] | None] = None

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotAuthenticatedError(DomainError):
    status_code = 401
    code = ErrorCode.NOT_AUTHENTICATED
    default_message = "Tu sesión no es válida o expiró. Ingresa de nuevo."
    headers: ClassVar[Mapping[str, str] | None] = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(DomainError):
    status_code = 403
    code = ErrorCode.FORBIDDEN
    default_message = "Tu perfil no permite realizar esta operación."


class NotFoundError(DomainError):
    status_code = 404
    code = ErrorCode.NOT_FOUND
    default_message = "No se encontró lo que buscas."


class AlreadyTakenError(DomainError):
    status_code = 409
    code = ErrorCode.ALREADY_TAKEN
    default_message = "Este ticket ya fue tomado por otro agente."


class ActionNotAllowedError(DomainError):
    status_code = 409
    code = ErrorCode.ACTION_NOT_ALLOWED
    default_message = "Esta acción no está permitida en este momento."


class InvalidFieldError(Exception):
    """Un campo bien formado que incumple una regla que solo la base puede verificar; responde 422."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(message)
