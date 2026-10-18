from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select, update

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import list_events
from droidesk_api.core.db import persisted_id
from droidesk_api.core.errors import ActionNotAllowedError, AlreadyTakenError
from droidesk_api.identity.models import User
from droidesk_api.sla.calendar import BusinessCalendar, BusinessHours
from droidesk_api.tickets.enums import Priority, TicketStatus
from droidesk_api.tickets.lifecycle import TicketAction
from droidesk_api.tickets.models import Comment, Ticket
from droidesk_api.tickets.schemas import CommentCreate, TicketUpdate
from droidesk_api.tickets.service import TicketService
from tests.factories import (
    AGENT_ID,
    CREATED_AT,
    OTHER_AGENT_ID,
    REQUESTER_ID,
    add_ticket,
    add_ticket_in,
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


def change_by_someone_else(
    engine: Engine, ticket_id: int, **values: Any
) -> Callable[[], None]:
    """El cambio de otra sesión sobre el ticket, para que `RacingClock` lo haga en plena operación."""

    def change() -> None:
        with Session(engine) as other_session:
            other_session.exec(
                update(Ticket).where(col(Ticket.id) == ticket_id).values(**values)
            )
            other_session.commit()

    return change


@pytest.mark.usefixtures("demo_data")
class TestCompetingChange:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return persisted_id(add_ticket(session))

    @pytest.fixture
    def owner(self, session: Session) -> User:
        return session.get_one(User, REQUESTER_ID)

    def take_by_another_agent(
        self, engine: Engine, ticket_id: int
    ) -> Callable[[], None]:
        return change_by_someone_else(
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
        cancel = change_by_someone_else(
            engine, ticket_id, status=TicketStatus.CANCELLED, cancelled_at=CREATED_AT
        )
        agent = session.get_one(User, AGENT_ID)
        with pytest.raises(ActionNotAllowedError, match="ya no está disponible"):
            TicketService(
                session, RacingClock(CREATED_AT, cancel), CALENDAR
            ).apply_transition(agent, ticket_id, TicketAction.TAKE)


@pytest.mark.usefixtures("demo_data")
class TestCommentOnAHeldTicketThatChangesFirst:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return persisted_id(add_ticket_in(session, TicketStatus.ON_HOLD))

    @pytest.fixture
    def owner(self, session: Session) -> User:
        return session.get_one(User, REQUESTER_ID)

    @pytest.fixture
    def agent_resumes(self, engine: Engine, ticket_id: int) -> Callable[[], None]:
        return change_by_someone_else(
            engine, ticket_id, status=TicketStatus.IN_PROGRESS, on_hold_since=None
        )

    def test_the_comment_is_rejected_with_the_state_conflict(
        self,
        session: Session,
        owner: User,
        ticket_id: int,
        agent_resumes: Callable[[], None],
    ) -> None:
        service = TicketService(
            session, RacingClock(CREATED_AT, agent_resumes), CALENDAR
        )
        with pytest.raises(ActionNotAllowedError, match="mientras escribías"):
            service.add_comment(owner, ticket_id, CommentCreate(body="Respuesta"))

    def test_the_loser_leaves_neither_comment_nor_events(
        self,
        session: Session,
        owner: User,
        ticket_id: int,
        agent_resumes: Callable[[], None],
    ) -> None:
        service = TicketService(
            session, RacingClock(CREATED_AT, agent_resumes), CALENDAR
        )
        with pytest.raises(ActionNotAllowedError):
            service.add_comment(owner, ticket_id, CommentCreate(body="Respuesta"))
        session.rollback()
        assert (
            list(session.exec(select(Comment))),
            list_events(session, ticket_id),
        ) == ([], [])


FINAL_CHANGES = [
    pytest.param(
        TicketStatus.OPEN,
        {"status": TicketStatus.CANCELLED, "cancelled_at": CREATED_AT},
        id="cancelled-while-open",
    ),
    pytest.param(
        TicketStatus.RESOLVED,
        {"status": TicketStatus.CLOSED, "closed_at": CREATED_AT},
        id="closed-while-resolved",
    ),
]


@pytest.mark.usefixtures("demo_data")
@pytest.mark.parametrize(("status", "final_values"), FINAL_CHANGES)
class TestCommentOnATicketThatEndsFirst:
    @pytest.fixture
    def ticket_id(self, session: Session, status: TicketStatus) -> int:
        return persisted_id(add_ticket_in(session, status))

    @pytest.fixture
    def service(
        self,
        session: Session,
        engine: Engine,
        ticket_id: int,
        final_values: dict[str, Any],
    ) -> TicketService:
        end = change_by_someone_else(engine, ticket_id, **final_values)
        return TicketService(session, RacingClock(CREATED_AT, end), CALENDAR)

    def comment_by_the_agent(
        self, service: TicketService, session: Session, ticket_id: int
    ) -> None:
        agent = session.get_one(User, AGENT_ID)
        service.add_comment(agent, ticket_id, CommentCreate(body="¿Sigue fallando?"))

    def test_the_comment_is_rejected_with_the_state_conflict(
        self, service: TicketService, session: Session, ticket_id: int
    ) -> None:
        with pytest.raises(ActionNotAllowedError, match="mientras escribías"):
            self.comment_by_the_agent(service, session, ticket_id)

    def test_the_loser_leaves_neither_comment_nor_events(
        self, service: TicketService, session: Session, ticket_id: int
    ) -> None:
        with pytest.raises(ActionNotAllowedError):
            self.comment_by_the_agent(service, session, ticket_id)
        session.rollback()
        assert (
            list(session.exec(select(Comment))),
            list_events(session, ticket_id),
        ) == ([], [])

    def test_the_ticket_keeps_the_final_status(
        self,
        service: TicketService,
        session: Session,
        ticket_id: int,
        final_values: dict[str, Any],
    ) -> None:
        with pytest.raises(ActionNotAllowedError):
            self.comment_by_the_agent(service, session, ticket_id)
        session.expire_all()
        assert session.get_one(Ticket, ticket_id).status == final_values["status"]


@pytest.mark.usefixtures("demo_data")
class TestCommentUpdatesTheTicket:
    @pytest.mark.parametrize("author_id", [REQUESTER_ID, AGENT_ID])
    def test_the_update_time_is_the_instant_of_the_comment(
        self, session: Session, author_id: int
    ) -> None:
        ticket_id = persisted_id(add_ticket_in(session, TicketStatus.IN_PROGRESS))
        clock = FakeClock(CREATED_AT + timedelta(hours=2))
        TicketService(session, clock, CALENDAR).add_comment(
            session.get_one(User, author_id), ticket_id, CommentCreate(body="Hola")
        )
        session.expire_all()
        assert session.get_one(Ticket, ticket_id).updated_at == clock.now()


# Lo que otra sesión cambia entre que se lee el ticket y se escribe la prioridad.
COMPETING_CHANGES = [
    pytest.param({"priority": Priority.LOW}, id="another-agent-changed-the-priority"),
    pytest.param(
        {"status": TicketStatus.RESOLVED, "resolved_at": CREATED_AT},
        id="resolved-first",
    ),
    pytest.param({"sla_paused_minutes": 60}, id="a-wait-was-added-first"),
]


@pytest.mark.usefixtures("demo_data")
@pytest.mark.parametrize("competing_values", COMPETING_CHANGES)
class TestPriorityChangeThatLosesTheRace:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return persisted_id(add_ticket_in(session, TicketStatus.IN_PROGRESS))

    @pytest.fixture
    def deadline_before(self, session: Session, ticket_id: int) -> datetime:
        return session.get_one(Ticket, ticket_id).sla_due_at

    @pytest.fixture
    def service(
        self,
        session: Session,
        engine: Engine,
        ticket_id: int,
        competing_values: dict[str, Any],
    ) -> TicketService:
        competing = change_by_someone_else(engine, ticket_id, **competing_values)
        return TicketService(session, RacingClock(CREATED_AT, competing), CALENDAR)

    def raise_to_critical(
        self, service: TicketService, session: Session, ticket_id: int
    ) -> None:
        agent = session.get_one(User, AGENT_ID)
        service.change_priority(
            agent, ticket_id, TicketUpdate(priority=Priority.CRITICAL)
        )

    def test_is_rejected_with_the_state_conflict(
        self, service: TicketService, session: Session, ticket_id: int
    ) -> None:
        with pytest.raises(ActionNotAllowedError, match="mientras ajustabas"):
            self.raise_to_critical(service, session, ticket_id)

    def test_leaves_no_event(
        self, service: TicketService, session: Session, ticket_id: int
    ) -> None:
        with pytest.raises(ActionNotAllowedError):
            self.raise_to_critical(service, session, ticket_id)
        session.rollback()
        assert list_events(session, ticket_id) == []

    def test_does_not_overwrite_what_the_other_session_wrote(
        self,
        service: TicketService,
        session: Session,
        ticket_id: int,
        deadline_before: datetime,
    ) -> None:
        with pytest.raises(ActionNotAllowedError):
            self.raise_to_critical(service, session, ticket_id)
        session.expire_all()
        ticket = session.get_one(Ticket, ticket_id)
        assert (ticket.priority is Priority.CRITICAL, ticket.sla_due_at) == (
            False,
            deadline_before,
        )
