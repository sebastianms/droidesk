from typing import Any, cast

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from droidesk_api.core.errors import DomainError, ErrorCode, InvalidFieldError


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


RESPONSE_DESCRIPTIONS = {
    401: "No autenticado: falta el token, es inválido o expiró.",
    403: "El perfil del usuario no permite la operación.",
    404: "No encontrado. Un ticket ajeno se informa igual que uno inexistente.",
    409: "Conflicto: otro agente tomó el ticket, o la acción no está permitida en el estado actual.",
}


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {
        status: {"model": ErrorBody, "description": RESPONSE_DESCRIPTIONS[status]}
        for status in statuses
    }


async def handle_domain_error(_request: Request, error: Exception) -> JSONResponse:
    domain_error = cast(DomainError, error)  # registrado solo para DomainError
    body = ErrorBody(code=domain_error.code, message=domain_error.message)
    return JSONResponse(
        status_code=domain_error.status_code,
        content=body.model_dump(mode="json"),
        headers=domain_error.headers,
    )


async def handle_validation_error(_request: Request, error: Exception) -> JSONResponse:
    """Igual que el 422 de FastAPI, pero sin `input`: eco de lo que envió el cliente, p. ej. una contraseña."""
    validation_error = cast(RequestValidationError, error)  # registrado solo para él
    details = [
        {key: value for key, value in detail.items() if key != "input"}
        for detail in validation_error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(details)},
    )


async def handle_invalid_field(_request: Request, error: Exception) -> JSONResponse:
    """Responde con la misma forma que el 422 de FastAPI, para que la web trate ambos igual."""
    invalid_field = cast(InvalidFieldError, error)  # registrado solo para él
    detail = [
        {
            "type": "value_error",
            "loc": ["body", invalid_field.field],
            "msg": invalid_field.message,
        }
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail}
    )
