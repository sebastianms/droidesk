from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends
from jwt.types import Options

from droidesk_api.core.clock import Clock, ClockDep
from droidesk_api.core.config import SettingsDep
from droidesk_api.core.errors import NotAuthenticatedError

ALGORITHM = "HS256"
REQUIRED_CLAIMS = ["sub", "iat", "exp"]
TOKEN_LIFETIME = timedelta(hours=8)


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: datetime


class TokenService:
    def __init__(self, secret: str, clock: Clock) -> None:
        self._secret = secret
        self._clock = clock

    def issue(self, user_id: int) -> AccessToken:
        issued_at = self._clock.now().replace(microsecond=0)
        expires_at = issued_at + TOKEN_LIFETIME
        claims = {
            "sub": str(user_id),
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return AccessToken(
            jwt.encode(claims, self._secret, algorithm=ALGORITHM), expires_at
        )

    def read_user_id(self, token: str) -> int:
        claims = self._decode(token)
        if claims["exp"] <= self._clock.now().timestamp():
            raise NotAuthenticatedError
        try:
            return int(claims["sub"])
        except ValueError:
            raise NotAuthenticatedError from None

    def _decode(self, token: str) -> dict[str, Any]:
        # PyJWT valida exp e iat con el reloj real; aquí se comparan con el reloj inyectado.
        options: Options = {
            "require": REQUIRED_CLAIMS,
            "verify_exp": False,
            "verify_iat": False,
        }
        try:
            return jwt.decode(
                token, self._secret, algorithms=[ALGORITHM], options=options
            )
        except jwt.InvalidTokenError:
            raise NotAuthenticatedError from None


def get_token_service(settings: SettingsDep, clock: ClockDep) -> TokenService:
    return TokenService(settings.jwt_secret.get_secret_value(), clock)


TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
