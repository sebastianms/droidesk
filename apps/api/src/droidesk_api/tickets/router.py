from fastapi import APIRouter, Depends
from sqlmodel import col, select

from droidesk_api.core.db import SessionDep
from droidesk_api.core.http_errors import error_responses
from droidesk_api.identity.authorization import get_current_user
from droidesk_api.tickets import schemas
from droidesk_api.tickets.models import Category

router = APIRouter(
    prefix="/api/v1", tags=["tickets"], dependencies=[Depends(get_current_user)]
)


@router.get("/categories", responses=error_responses(401))
def list_categories(session: SessionDep) -> list[schemas.Category]:
    categories = session.exec(select(Category).order_by(col(Category.id)))
    return [schemas.Category.model_validate(category) for category in categories]
