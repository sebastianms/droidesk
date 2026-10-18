from collections.abc import Callable
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, update

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import list_events
from droidesk_api.core.db import persisted_id
from droidesk_api.core.errors import ActionNotAllowedError, AlreadyTakenError
from droidesk_api.identity.models import User
from droidesk_api.sla.calendar import BusinessCalendar, BusinessHours
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.lifecycle import TicketAction
from droidesk_api.tickets.models import Ticket
from droidesk_api.tickets.service import TicketService
from tests.factories import (
    AGENT_ID,
    CREATED_AT,
    OTHER_AGENT_ID,
    REQUESTER_ID,
    add_ticket,
)
from tests.fakes import FakeClock

CALENDAR = BusinessCalendar(
    ZoneInfo("America/Santiago"), BusinessHours(time(9, 0), time(18, 0))
)


class RacingClock(FakeClock):
    """Hace un cambio ajeno la primera vez que el servicio pide la hora: tras leer el ticket, antes de escribirlo."""

    def __init__(self, now: datetime, competing_change: Callable[[], None]) -> None:
        super().__init__(now)
        self._competing_change: Callable[[], None] | None = competing_change

    def now(self) -> datetime:
        if self._competing_change is not None:
            change, self._competing_change = self._competing_change, None
            change()
        return super().now()


@pytest.mark.usefixtures("demo_data")
class TestCompetingChange:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return persisted_id(add_ticket(session))

    @pytest.fixture
    def owner(self, session: Session) -> User:
        return session.get_one(User, REQUESTER_ID)

    def change_by_someone_else(
        self, engine: Engine, ticket_id: int, **values: Any
    ) -> Callable[[], None]:
        def change() -> None:
            with Session(engine) as other_session:
                other_session.exec(
                    update(Ticket).where(col(Ticket.id) == ticket_id).values(**values)
                )
                other_session.commit()

        return change

    def take_by_another_agent(
        self, engine: Engine, ticket_id: int
    ) -> Callable[[], None]:
        return self.change_by_someone_else(
            engine, ticket_id, status=TicketStatus.IN_PROGRESS, assignee_id=AGENT_ID
        )

    def test_a_cancellation_that_loses_the_race_is_rejected(
        self, session: Session, engine: Engine, owner: User, ticket_id: int
    ) -> None:
        clock = RacingClock(CREATED_AT, self.take_by_another_agent(engine, ticket_id))
        service = TicketService(session, clock, CALENDAR)
        with pytest.raises(ActionNotAllowedError, match="ya no está disponible"):
            service.apply_transition(owner, ticket_id, TicketAction.CANCEL)

    def test_the_winner_keeps_the_ticket_untouched_by_the_loser(
        self, session: Session, engine: Engine, owner: User, ticket_id: int
    ) -> None:
        clock = RacingClock(CREATED_AT, self.take_by_another_agent(engine, ticket_id))
        with pytest.raises(ActionNotAllowedError):
            TicketService(session, clock, CALENDAR).apply_transition(
                owner, ticket_id, TicketAction.CANCEL
            )
        session.expire_all()
        ticket = session.get_one(Ticket, ticket_id)
        assert (ticket.status, ticket.cancelled_at, ticket.assignee_id) == (
            TicketStatus.IN_PROGRESS,
            None,
            AGENT_ID,
        )

    def test_the_loser_leaves_no_event(
        self, session: Session, engine: Engine, owner: User, ticket_id: int
    ) -> None:
        clock = RacingClock(CREATED_AT, self.take_by_another_agent(engine, ticket_id))
        with pytest.raises(ActionNotAllowedError):
            TicketService(session, clock, CALENDAR).apply_transition(
                owner, ticket_id, TicketAction.CANCEL
            )
        assert [
            event.kind
            for event in list_events(session, ticket_id)
            if event.kind == EventKind.STATUS_CHANGED
        ] == []

    def test_a_take_that_loses_to_another_agent_is_reported_as_taken(
        self, session: Session, engine: Engine, ticket_id: int
    ) -> None:
        clock = RacingClock(CREATED_AT, self.take_by_another_agent(engine, ticket_id))
        loser = session.get_one(User, OTHER_AGENT_ID)
        with pytest.raises(AlreadyTakenError):
            TicketService(session, clock, CALENDAR).apply_transition(
                loser, ticket_id, TicketAction.TAKE
            )

    def test_a_take_that_loses_to_the_same_agent_is_not_reported_as_taken(
        self, session: Session, engine: Engine, ticket_id: int
    ) -> None:
        clock = RacingClock(CREATED_AT, self.take_by_another_agent(engine, ticket_id))
        double_click = session.get_one(User, AGENT_ID)
        with pytest.raises(ActionNotAllowedError, match="ya no está disponible"):
            TicketService(session, clock, CALENDAR).apply_transition(
                double_click, ticket_id, TicketAction.TAKE
            )

    def test_a_take_that_loses_to_a_cancellation_is_not_reported_as_taken(
        self, session: Session, engine: Engine, ticket_id: int
    ) -> None:
        cancel = self.change_by_someone_else(
            engine, ticket_id, status=TicketStatus.CANCELLED, cancelled_at=CREATED_AT
        )
        agent = session.get_one(User, AGENT_ID)
        with pytest.raises(ActionNotAllowedError, match="ya no está disponible"):
            TicketService(
                session, RacingClock(CREATED_AT, cancel), CALENDAR
            ).apply_transition(agent, ticket_id, TicketAction.TAKE)
