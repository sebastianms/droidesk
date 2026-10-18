from pydantic import BaseModel, ConfigDict

from droidesk_api.sla.enums import TargetUnit
from droidesk_api.tickets.enums import Priority


class SlaPolicy(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    priority: Priority
    rank: int
    label: str
    description: str
    target_amount: int
    target_unit: TargetUnit
