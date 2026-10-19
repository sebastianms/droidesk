from collections import Counter
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, col, func, select

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.models import TicketEvent
from droidesk_api.audit.recorder import list_events
from droidesk_api.core.config import Settings
from droidesk_api.core.db import persisted_id
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.seed import seed_demo_tickets
from droidesk_api.sla.calendar import BusinessCalendar
from droidesk_api.sla.dependencies import get_calendar
from droidesk_api.sla.status import SlaState
from droidesk_api.tickets.comments import list_comments
from droidesk_api.tickets.enums import Priority, TicketStatus
from droidesk_api.tickets.models import Comment, Ticket
from droidesk_api.tickets.service import TicketService
from tests.conftest import MONDAY_MORNING
from tests.factories import AGENT_ID, add_ticket
from tests.fakes import FakeClock

SANTIAGO = ZoneInfo("America/Santiago")
REQUESTER_IDS = {1, 2, 3, 4}
AGENT_IDS = {5, 6, 7}
CATEGORY_IDS = {1, 2, 3, 4, 5}
# Cada escenario en el orden en que se declara: estado, prioridad final y SLA.
EXPECTED_OUTCOMES = [
    (TicketStatus.OPEN, Priority.CRITICAL, SlaState.ON_TRACK),
    (TicketStatus.OPEN, Priority.MEDIUM, SlaState.ON_TRACK),
    (TicketStatus.OPEN, Priority.LOW, SlaState.ON_TRACK),
    (TicketStatus.OPEN, Priority.HIGH, SlaState.BREACHED),
    (TicketStatus.IN_PROGRESS, Priority.MEDIUM, SlaState.ON_TRACK),
    (TicketStatus.ON_HOLD, Priority.MEDIUM, SlaState.PAUSED),
    (TicketStatus.RESOLVED, Priority.HIGH, SlaState.MET),
    (TicketStatus.CLOSED, Priority.MEDIUM, SlaState.MET),
    (TicketStatus.CANCELLED, Priority.LOW, None),
]


def local(day: int, hour: int, minute: int = 0) -> datetime:
    """Un instante de octubre de 2026 (el lunes 19 es el día de los ejemplos), dicho en la hora de la organización."""
    return datetime(2026, 10, day, hour, minute, tzinfo=SANTIAGO).astimezone(UTC)


# Fines de semana, justo antes de abrir y justo antes de cerrar: donde el calendario hábil se pone difícil.
MOMENTS = {
    "saturday 03:00": local(24, 3),
    "monday 09:05": local(19, 9, 5),
    "tuesday 12:00": local(20, 12),
    "wednesday 17:59": local(21, 17, 59),
    "friday 18:00": local(23, 18),
    "sunday 23:59": local(25, 23, 59),
}


@pytest.fixture(params=list(MOMENTS))
def moment(request: pytest.FixtureRequest) -> datetime:
    return MOMENTS[request.param]


@pytest.fixture
def calendar(settings: Settings) -> BusinessCalendar:
    return get_calendar(settings)


@pytest.fixture
def seeded(session: Session, demo_data: None, calendar: BusinessCalendar) -> None:
    seed_demo_tickets(session, calendar, FakeClock(MONDAY_MORNING))


def all_tickets(session: Session) -> list[Ticket]:
    return list(session.exec(select(Ticket).order_by(col(Ticket.id))))


def count(session: Session, model: type[Ticket | Comment | TicketEvent]) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def totals(session: Session) -> tuple[int, int, int]:
    return (
        count(session, Ticket),
        count(session, Comment),
        count(session, TicketEvent),
    )


def status_in_history(session: Session, ticket: Ticket) -> str:
    """El estado al que llevó el último cambio de la historia; sin cambios, el ticket sigue abierto."""
    changes = [
        event.to_value
        for event in list_events(session, persisted_id(ticket))
        if event.kind == EventKind.STATUS_CHANGED
    ]
    return changes[-1] if changes and changes[-1] else TicketStatus.OPEN.value


def instants_of(session: Session, ticket: Ticket) -> list[datetime]:
    """Todas las fechas de lo ocurrido en el ticket, salvo su vencimiento, que sí queda en el futuro."""
    ticket_id = persisted_id(ticket)
    stamped = [
        ticket.created_at,
        ticket.updated_at,
        ticket.on_hold_since,
        ticket.resolved_at,
        ticket.closed_at,
        ticket.cancelled_at,
    ]
    return [
        *(instant for instant in stamped if instant is not None),
        *(event.created_at for event in list_events(session, ticket_id)),
        *(comment.created_at for comment in list_comments(session, ticket_id)),
    ]


@pytest.mark.usefixtures("demo_data")
class TestLoading:
    def test_loads_the_example_tickets(
        self, session: Session, calendar: BusinessCalendar
    ) -> None:
        assert seed_demo_tickets(session, calendar, FakeClock(MONDAY_MORNING)) is True

    @pytest.mark.usefixtures("seeded")
    def test_loading_again_reports_that_it_did_nothing(
        self, session: Session, calendar: BusinessCalendar
    ) -> None:
        assert seed_demo_tickets(session, calendar, FakeClock(MONDAY_MORNING)) is False

    @pytest.mark.usefixtures("seeded")
    def test_loading_again_adds_nothing(
        self, session: Session, calendar: BusinessCalendar
    ) -> None:
        before = totals(session)
        seed_demo_tickets(session, calendar, FakeClock(MONDAY_MORNING))
        assert totals(session) == before

    def test_a_database_that_already_has_a_ticket_is_left_alone(
        self, session: Session, calendar: BusinessCalendar
    ) -> None:
        add_ticket(session)
        seed_demo_tickets(session, calendar, FakeClock(MONDAY_MORNING))
        assert count(session, Ticket) == 1


@pytest.mark.usefixtures("seeded")
class TestWhatTheDemoShows:
    def test_has_the_expected_mix_of_statuses(self, session: Session) -> None:
        statuses = Counter(ticket.status for ticket in all_tickets(session))
        assert dict(statuses) == {
            TicketStatus.OPEN: 4,
            TicketStatus.IN_PROGRESS: 1,
            TicketStatus.ON_HOLD: 1,
            TicketStatus.RESOLVED: 1,
            TicketStatus.CLOSED: 1,
            TicketStatus.CANCELLED: 1,
        }

    def test_involves_the_four_requesters(self, session: Session) -> None:
        requesters = {ticket.requester_id for ticket in all_tickets(session)}
        assert requesters == REQUESTER_IDS

    def test_involves_the_three_agents(self, session: Session) -> None:
        agents = {ticket.assignee_id for ticket in all_tickets(session)}
        assert agents == AGENT_IDS | {None}

    def test_uses_the_five_categories(self, session: Session) -> None:
        categories = {ticket.category_id for ticket in all_tickets(session)}
        assert categories == CATEGORY_IDS

    def test_a_quoted_reply_answers_a_comment_of_the_same_ticket(
        self, session: Session
    ) -> None:
        reply = session.exec(
            select(Comment).where(col(Comment.reply_to_id).is_not(None))
        ).one()
        assert session.get_one(Comment, reply.reply_to_id).ticket_id == reply.ticket_id

    def test_an_agent_adjusted_a_priority(self, session: Session) -> None:
        event = session.exec(
            select(TicketEvent).where(
                col(TicketEvent.kind) == EventKind.PRIORITY_CHANGED
            )
        ).one()
        assert session.get_one(User, event.actor_id).role == Role.AGENT

    def test_the_last_status_change_of_each_history_is_the_ticket_status(
        self, session: Session
    ) -> None:
        tickets = all_tickets(session)
        assert [status_in_history(session, t) for t in tickets] == [
            t.status for t in tickets
        ]

    def test_every_history_starts_with_the_creation(self, session: Session) -> None:
        first_kinds = {
            list_events(session, persisted_id(ticket))[0].kind
            for ticket in all_tickets(session)
        }
        assert first_kinds == {EventKind.CREATED}

    def test_each_history_lists_its_events_in_the_order_they_were_recorded(
        self, session: Session
    ) -> None:
        ids_by_ticket = [
            [
                persisted_id(event)
                for event in list_events(session, persisted_id(ticket))
            ]
            for ticket in all_tickets(session)
        ]
        assert all(ids == sorted(ids) for ids in ids_by_ticket)

    def test_each_conversation_lists_its_comments_in_the_order_they_were_written(
        self, session: Session
    ) -> None:
        ids_by_ticket = [
            [
                persisted_id(comment)
                for comment in list_comments(session, persisted_id(ticket))
            ]
            for ticket in all_tickets(session)
        ]
        assert all(ids == sorted(ids) for ids in ids_by_ticket)


class TestWhateverTheMoment:
    @pytest.fixture
    def seeded_at(
        self,
        session: Session,
        demo_data: None,
        calendar: BusinessCalendar,
        moment: datetime,
    ) -> None:
        seed_demo_tickets(session, calendar, FakeClock(moment))

    @pytest.mark.usefixtures("seeded_at")
    def test_every_ticket_ends_in_the_expected_state(
        self, session: Session, calendar: BusinessCalendar, moment: datetime
    ) -> None:
        service = TicketService(session, FakeClock(moment), calendar)
        agent = session.get_one(User, AGENT_ID)
        details = [
            service.get_ticket_for(agent, persisted_id(ticket))
            for ticket in all_tickets(session)
        ]
        assert [
            (detail.status, detail.priority, detail.sla.state) for detail in details
        ] == EXPECTED_OUTCOMES

    @pytest.mark.usefixtures("seeded_at")
    def test_nothing_happens_after_the_load(
        self, session: Session, moment: datetime
    ) -> None:
        latest = max(
            instant
            for ticket in all_tickets(session)
            for instant in instants_of(session, ticket)
        )
        assert latest <= moment
