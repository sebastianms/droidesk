from fastapi import APIRouter, Depends
from sqlmodel import col, select

from droidesk_api.core.db import SessionDep
from droidesk_api.core.http_errors import error_responses
from droidesk_api.identity.authorization import get_current_user
from droidesk_api.sla import schemas
from droidesk_api.sla.models import SlaPolicy

router = APIRouter(
    prefix="/api/v1", tags=["sla"], dependencies=[Depends(get_current_user)]
)


@router.get("/sla-policies", responses=error_responses(401))
def list_sla_policies(session: SessionDep) -> list[schemas.SlaPolicy]:
    policies = session.exec(select(SlaPolicy).order_by(col(SlaPolicy.rank)))
    return [schemas.SlaPolicy.model_validate(policy) for policy in policies]
