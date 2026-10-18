from sqlmodel import Field, SQLModel

from droidesk_api.core.db import text_enum
from droidesk_api.identity.enums import Role

USERNAME_MAX_LENGTH = 50
NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=USERNAME_MAX_LENGTH, unique=True, index=True)
    name: str = Field(max_length=NAME_MAX_LENGTH)
    email: str = Field(max_length=EMAIL_MAX_LENGTH, unique=True)
    role: Role = Field(sa_type=text_enum(Role))
