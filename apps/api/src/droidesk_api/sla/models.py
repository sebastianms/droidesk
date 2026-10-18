from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from droidesk_api.core.db import text_enum
from droidesk_api.sla.enums import TargetUnit
from droidesk_api.tickets.enums import Priority

LABEL_MAX_LENGTH = 20
DESCRIPTION_MAX_LENGTH = 200


class SlaPolicy(SQLModel, table=True):
    __tablename__ = "sla_policies"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_amount_positive"),
    )

    priority: Priority = Field(sa_type=text_enum(Priority), primary_key=True)
    rank: int
    label: str = Field(max_length=LABEL_MAX_LENGTH)
    description: str = Field(max_length=DESCRIPTION_MAX_LENGTH)
    target_amount: int
    target_unit: TargetUnit = Field(sa_type=text_enum(TargetUnit))
