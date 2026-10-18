import re
from datetime import time
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends
from pydantic import BeforeValidator, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from droidesk_api.sla.calendar import BusinessHours

MIN_JWT_SECRET_BYTES = 32
BUSINESS_HOURS_PATTERN = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")


def parse_business_hours(raw: object) -> object:
    if not isinstance(raw, str):
        return raw
    match = BUSINESS_HOURS_PATTERN.fullmatch(raw.strip())
    if match is None:
        raise ValueError(
            "La jornada debe tener el formato HH:MM-HH:MM, por ejemplo 09:00-18:00."
        )
    opens, closes = (time.fromisoformat(part) for part in match.groups())
    return BusinessHours(opens=opens, closes=closes)


class DatabaseSettings(BaseSettings):
    """Lo mínimo que necesitan las migraciones: no exige secretos."""

    model_config = SettingsConfigDict(
        env_prefix="DROIDESK_", extra="ignore", hide_input_in_errors=True
    )

    database_url: str = "sqlite:////data/droidesk.db"


class Settings(DatabaseSettings):
    jwt_secret: SecretStr
    seed_demo_data: bool = True
    timezone: ZoneInfo = ZoneInfo("America/Santiago")
    business_hours: Annotated[
        BusinessHours, NoDecode, BeforeValidator(parse_business_hours)
    ] = BusinessHours(opens=time(9, 0), closes=time(18, 0))

    @field_validator("jwt_secret")
    @classmethod
    def require_long_secret(cls, secret: SecretStr) -> SecretStr:
        if len(secret.get_secret_value().encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"El secreto debe tener al menos {MIN_JWT_SECRET_BYTES} bytes."
            )
        return secret


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
