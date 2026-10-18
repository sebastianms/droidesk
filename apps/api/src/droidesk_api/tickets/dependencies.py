from typing import Annotated

from fastapi import Depends

from droidesk_api.core.clock import ClockDep
from droidesk_api.core.db import SessionDep
from droidesk_api.sla.dependencies import CalendarDep
from droidesk_api.tickets.service import TicketService


def get_ticket_service(
    session: SessionDep, clock: ClockDep, calendar: CalendarDep
) -> TicketService:
    return TicketService(session, clock, calendar)


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]
