import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine, event
from sqlmodel import Session

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import list_events
from droidesk_api.identity.enums import Role
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.lifecycle import TRANSITIONS
from tests.api.helpers import (
    TICKETS_URL,
    LoginAs,
    add_ticket_id,
    add_ticket_in_id,
    post_ticket,
    reload,
    transitions_url,
)
from tests.factories import (
    AGENT_ID,
    AGENT_USERNAME,
    CREATED_AT,
    OTHER_AGENT_ID,
    OTHER_AGENT_USERNAME,
    OTHER_REQUESTER_ID,
    OTHER_REQUESTER_USERNAME,
    REQUESTER_ID,
    REQUESTER_USERNAME,
    THIRD_AGENT_USERNAME,
    add_ticket,
    add_ticket_in,
)
from tests.fakes import FakeClock

Act = Callable[[str, int, str], Response]
Read = Callable[[str, int], Response]


class ListAs(Protocol):
    def __call__(self, username: str, view: str | None = None) -> Response: ...


HOUR = timedelta(hours=1)
DAY = timedelta(hours=24)
HIGH_DEADLINE = (
    "2026-10-20T13:05:00Z"  # martes 10:05 local: 1 día hábil desde el lunes 10:05
)
USERNAME_BY_ROLE = {Role.AGENT: AGENT_USERNAME, Role.REQUESTER: REQUESTER_USERNAME}
OTHER_USERNAME_BY_ROLE = {
    Role.AGENT: REQUESTER_USERNAME,
    Role.REQUESTER: AGENT_USERNAME,
}


# Los tokens duran 8 horas con el reloj inyectado: cada llamada ingresa de nuevo,
# para que los tests puedan adelantar el reloj días enteros.
@pytest.fixture
def act(client: TestClient, login_as: LoginAs) -> Act:
    def perform(username: str, ticket_id: int, action: str) -> Response:
        return client.post(
            transitions_url(ticket_id),
            headers=login_as(username),
            json={"action": action},
        )

    return perform


@pytest.fixture
def read(client: TestClient, login_as: LoginAs) -> Read:
    def fetch(username: str, ticket_id: int) -> Response:
        return client.get(f"{TICKETS_URL}/{ticket_id}", headers=login_as(username))

    return fetch


@pytest.fixture
def list_as(client: TestClient, login_as: LoginAs) -> ListAs:
    def fetch(username: str, view: str | None = None) -> Response:
        params = {} if view is None else {"view": view}
        return client.get(TICKETS_URL, params=params, headers=login_as(username))

    return fetch


def titles(response: Response) -> list[str]:
    return [ticket["title"] for ticket in response.json()]


def errors(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


def event_trail(
    session: Session, ticket_id: int
) -> list[tuple[EventKind, int, str | None, str | None]]:
    return [
        (row.kind, row.actor_id, row.from_value, row.to_value)
        for row in list_events(session, ticket_id)
    ]


@pytest.mark.usefixtures("demo_data")
class TestQueue:
    def test_the_queue_is_the_default_view_of_an_agent(
        self, list_as: ListAs, session: Session
    ) -> None:
        add_ticket(session)
        assert list_as(AGENT_USERNAME).json() == list_as(AGENT_USERNAME, "queue").json()

    def test_lists_the_tickets_of_every_requester(
        self, list_as: ListAs, session: Session
    ) -> None:
        add_ticket(session, title="De Ana", sla_due_at=CREATED_AT + HOUR)
        add_ticket(
            session,
            title="De Bruno",
            requester_id=OTHER_REQUESTER_ID,
            sla_due_at=CREATED_AT + 2 * HOUR,
        )
        assert titles(list_as(AGENT_USERNAME, "queue")) == ["De Ana", "De Bruno"]

    @pytest.mark.parametrize(
        "status",
        [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.ON_HOLD,
            TicketStatus.RESOLVED,
        ],
    )
    def test_includes_every_unfinished_status(
        self, list_as: ListAs, session: Session, status: TicketStatus
    ) -> None:
        add_ticket_in(session, status, title=status.value)
        assert titles(list_as(AGENT_USERNAME, "queue")) == [status.value]

    @pytest.mark.parametrize("status", [TicketStatus.CLOSED, TicketStatus.CANCELLED])
    def test_leaves_out_the_final_statuses(
        self, list_as: ListAs, session: Session, status: TicketStatus
    ) -> None:
        add_ticket_in(session, status)
        assert list_as(AGENT_USERNAME, "queue").json() == []

    def test_an_entry_shows_status_requester_category_and_assignee(
        self, list_as: ListAs, session: Session
    ) -> None:
        add_ticket_in(session, TicketStatus.IN_PROGRESS, category_id=2)
        (entry,) = list_as(AGENT_USERNAME, "queue").json()
        assert (
            entry["status"],
            entry["requester"],
            entry["category"],
            entry["assignee"],
        ) == (
            "in_progress",
            {"id": REQUESTER_ID, "name": "Ana Rojas"},
            {"id": 2, "name": "Software"},
            {"id": AGENT_ID, "name": "Elena Vidal"},
        )

    def test_an_entry_on_hold_shows_its_sla_as_paused(
        self, list_as: ListAs, session: Session
    ) -> None:
        add_ticket_in(session, TicketStatus.ON_HOLD)
        (entry,) = list_as(AGENT_USERNAME, "queue").json()
        assert entry["sla"] == {"state": "paused", "due_at": None}

    def test_an_agent_cannot_ask_for_the_requester_view(self, list_as: ListAs) -> None:
        assert errors(list_as(AGENT_USERNAME, "mine")) == (403, "forbidden")


@pytest.mark.usefixtures("demo_data")
class TestQueueOrder:
    @pytest.fixture
    def queue_titles(self, list_as: ListAs) -> Callable[[], list[str]]:
        return lambda: titles(list_as(AGENT_USERNAME, "queue"))

    def test_the_closest_deadline_comes_first(
        self, session: Session, queue_titles: Callable[[], list[str]]
    ) -> None:
        for name, hours in (("tarde", 3), ("pronto", 1), ("medio", 2)):
            add_ticket(session, title=name, sla_due_at=CREATED_AT + hours * HOUR)
        assert queue_titles() == ["pronto", "medio", "tarde"]

    def test_tickets_on_hold_come_after_the_running_ones(
        self, session: Session, queue_titles: Callable[[], list[str]]
    ) -> None:
        add_ticket_in(
            session, TicketStatus.ON_HOLD, title="espera", sla_due_at=CREATED_AT + HOUR
        )
        add_ticket(session, title="corriendo 3", sla_due_at=CREATED_AT + 3 * HOUR)
        add_ticket(session, title="corriendo 2", sla_due_at=CREATED_AT + 2 * HOUR)
        assert queue_titles() == ["corriendo 2", "corriendo 3", "espera"]

    def test_tickets_on_hold_are_ordered_by_deadline_among_themselves(
        self, session: Session, queue_titles: Callable[[], list[str]]
    ) -> None:
        for name, hours in (("espera tarde", 3), ("espera pronto", 1)):
            add_ticket_in(
                session,
                TicketStatus.ON_HOLD,
                title=name,
                sla_due_at=CREATED_AT + hours * HOUR,
            )
        assert queue_titles() == ["espera pronto", "espera tarde"]

    def test_the_oldest_comes_first_when_deadlines_are_equal(
        self, session: Session, queue_titles: Callable[[], list[str]]
    ) -> None:
        deadline = CREATED_AT + HOUR
        add_ticket(
            session, title="nuevo", sla_due_at=deadline, created_at=CREATED_AT - HOUR
        )
        add_ticket(
            session,
            title="antiguo",
            sla_due_at=deadline,
            created_at=CREATED_AT - 2 * HOUR,
        )
        assert queue_titles() == ["antiguo", "nuevo"]

    def test_a_full_tie_keeps_the_creation_order(
        self, session: Session, queue_titles: Callable[[], list[str]]
    ) -> None:
        for name in ("primero", "segundo", "tercero"):
            add_ticket(session, title=name)
        assert queue_titles() == ["primero", "segundo", "tercero"]

    def test_a_resolved_ticket_is_ordered_by_its_deadline_among_the_running(
        self, session: Session, queue_titles: Callable[[], list[str]]
    ) -> None:
        add_ticket(session, title="vence 3", sla_due_at=CREATED_AT + 3 * HOUR)
        add_ticket_in(
            session,
            TicketStatus.RESOLVED,
            title="resuelto 2",
            sla_due_at=CREATED_AT + 2 * HOUR,
        )
        add_ticket(session, title="vence 1", sla_due_at=CREATED_AT + HOUR)
        assert queue_titles() == ["vence 1", "resuelto 2", "vence 3"]


@pytest.mark.usefixtures("demo_data")
class TestAssigned:
    def test_lists_only_the_unfinished_tickets_assigned_to_the_agent(
        self, list_as: ListAs, session: Session
    ) -> None:
        for status in (
            TicketStatus.IN_PROGRESS,
            TicketStatus.ON_HOLD,
            TicketStatus.RESOLVED,
        ):
            add_ticket_in(session, status, title=status.value)
        add_ticket_in(session, TicketStatus.CLOSED, title="cerrado")
        add_ticket(session, title="sin asignar")
        add_ticket_in(
            session, TicketStatus.IN_PROGRESS, title="ajeno", assignee_id=OTHER_AGENT_ID
        )
        assert sorted(titles(list_as(AGENT_USERNAME, "assigned"))) == [
            "in_progress",
            "on_hold",
            "resolved",
        ]

    def test_each_agent_sees_only_their_own(
        self, list_as: ListAs, session: Session
    ) -> None:
        add_ticket_in(session, TicketStatus.IN_PROGRESS, title="de Elena")
        add_ticket_in(
            session,
            TicketStatus.IN_PROGRESS,
            title="de Felipe",
            assignee_id=OTHER_AGENT_ID,
        )
        assert titles(list_as(OTHER_AGENT_USERNAME, "assigned")) == ["de Felipe"]

    def test_follows_the_same_order_as_the_queue(
        self, list_as: ListAs, session: Session
    ) -> None:
        add_ticket_in(
            session, TicketStatus.ON_HOLD, title="espera", sla_due_at=CREATED_AT + HOUR
        )
        add_ticket_in(
            session,
            TicketStatus.IN_PROGRESS,
            title="tarde",
            sla_due_at=CREATED_AT + 3 * HOUR,
        )
        add_ticket_in(
            session,
            TicketStatus.IN_PROGRESS,
            title="pronto",
            sla_due_at=CREATED_AT + 2 * HOUR,
        )
        assert titles(list_as(AGENT_USERNAME, "assigned")) == [
            "pronto",
            "tarde",
            "espera",
        ]

    def test_is_empty_for_an_agent_without_tickets(self, list_as: ListAs) -> None:
        assert list_as(AGENT_USERNAME, "assigned").json() == []

    def test_a_taken_ticket_appears_in_the_view_of_whoever_took_it(
        self, act: Act, list_as: ListAs, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session, title="por tomar")
        act(AGENT_USERNAME, ticket_id, "take")
        assert titles(list_as(AGENT_USERNAME, "assigned")) == ["por tomar"]


@pytest.mark.usefixtures("demo_data")
class TestTake:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_id(session)

    def test_the_ticket_moves_to_in_progress(self, act: Act, ticket_id: int) -> None:
        response = act(AGENT_USERNAME, ticket_id, "take")
        assert (response.status_code, response.json()["status"]) == (200, "in_progress")

    def test_the_ticket_is_assigned_to_whoever_took_it(
        self, act: Act, ticket_id: int
    ) -> None:
        response = act(AGENT_USERNAME, ticket_id, "take")
        assert response.json()["assignee"] == {"id": AGENT_ID, "name": "Elena Vidal"}

    def test_the_assignment_is_stored(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "take")
        ticket = reload(session, ticket_id)
        assert (ticket.status, ticket.assignee_id) == (
            TicketStatus.IN_PROGRESS,
            AGENT_ID,
        )

    def test_the_update_time_is_the_current_instant(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(HOUR)
        act(AGENT_USERNAME, ticket_id, "take")
        assert reload(session, ticket_id).updated_at == clock.now()

    def test_taking_does_not_move_the_deadline(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        before = reload(session, ticket_id).sla_due_at
        act(AGENT_USERNAME, ticket_id, "take")
        assert reload(session, ticket_id).sla_due_at == before

    def test_records_the_assignment_and_then_the_status_change(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "take")
        assert event_trail(session, ticket_id) == [
            (EventKind.ASSIGNED, AGENT_ID, None, "Elena Vidal"),
            (EventKind.STATUS_CHANGED, AGENT_ID, "open", "in_progress"),
        ]

    def test_both_events_carry_the_instant_of_the_take(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(HOUR)
        act(AGENT_USERNAME, ticket_id, "take")
        assert {row.created_at for row in list_events(session, ticket_id)} == {
            clock.now()
        }

    def test_the_assigned_agent_is_offered_the_next_actions(
        self, act: Act, ticket_id: int
    ) -> None:
        response = act(AGENT_USERNAME, ticket_id, "take")
        assert response.json()["allowed_actions"] == [
            "hold",
            "resolve",
            "comment",
            "change_priority",
        ]

    def test_the_ticket_stays_in_the_queue_once_taken(
        self, act: Act, list_as: ListAs, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "take")
        assert len(list_as(OTHER_AGENT_USERNAME, "queue").json()) == 1

    def test_another_agent_is_told_the_ticket_was_taken(
        self, act: Act, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "take")
        response = act(OTHER_AGENT_USERNAME, ticket_id, "take")
        assert (response.status_code, response.json()) == (
            409,
            {
                "code": "already_taken",
                "message": "Este ticket ya fue tomado por otro agente.",
            },
        )

    def test_the_agent_that_lost_changes_nothing(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "take")
        act(OTHER_AGENT_USERNAME, ticket_id, "take")
        assert (
            reload(session, ticket_id).assignee_id,
            len(list_events(session, ticket_id)),
        ) == (AGENT_ID, 2)

    @pytest.mark.parametrize(
        "status",
        [
            TicketStatus.IN_PROGRESS,
            TicketStatus.ON_HOLD,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
        ],
    )
    def test_a_ticket_that_already_has_another_agent_is_reported_as_taken(
        self, act: Act, session: Session, status: TicketStatus
    ) -> None:
        taken_id = add_ticket_in_id(session, status)
        response = act(OTHER_AGENT_USERNAME, taken_id, "take")
        assert errors(response) == (409, "already_taken")

    def test_taking_the_ticket_you_already_hold_is_not_allowed(
        self, act: Act, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "take")
        response = act(AGENT_USERNAME, ticket_id, "take")
        assert errors(response) == (409, "action_not_allowed")

    def test_a_cancelled_ticket_cannot_be_taken(
        self, act: Act, session: Session
    ) -> None:
        cancelled_id = add_ticket_in_id(session, TicketStatus.CANCELLED)
        response = act(AGENT_USERNAME, cancelled_id, "take")
        assert (response.status_code, response.json()) == (
            409,
            {
                "code": "action_not_allowed",
                "message": "La acción «Tomar» no está disponible con el ticket en estado «Cancelado».",
            },
        )

    def test_a_requester_cannot_take(self, act: Act, ticket_id: int) -> None:
        response = act(REQUESTER_USERNAME, ticket_id, "take")
        assert errors(response) == (403, "forbidden")


@pytest.mark.usefixtures("demo_data")
class TestSimultaneousTake:
    """Varios agentes toman el mismo ticket a la vez, cada uno con su sesión de base de datos."""

    AGENTS = (AGENT_USERNAME, OTHER_AGENT_USERNAME, THIRD_AGENT_USERNAME)

    @pytest.fixture
    def everyone_reads_before_anyone_writes(self, engine: Engine) -> Iterator[None]:
        """Detiene a cada petición justo antes de su UPDATE hasta que todas leyeron el ticket abierto."""
        barrier = threading.Barrier(len(self.AGENTS), timeout=10)

        def wait_before_updating(statement: str, **_: Any) -> None:
            if statement.startswith("UPDATE tickets"):
                barrier.wait()

        event.listen(engine, "before_cursor_execute", wait_before_updating, named=True)
        yield
        event.remove(engine, "before_cursor_execute", wait_before_updating)

    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_id(session)

    @pytest.fixture
    def responses(
        self,
        client: TestClient,
        login_as: LoginAs,
        ticket_id: int,
        everyone_reads_before_anyone_writes: None,
    ) -> list[Response]:
        agent_headers = [login_as(username) for username in self.AGENTS]
        url = transitions_url(ticket_id)

        def take(headers: dict[str, str]) -> Response:
            return client.post(url, headers=headers, json={"action": "take"})

        with ThreadPoolExecutor(max_workers=len(agent_headers)) as pool:
            return list(pool.map(take, agent_headers))

    def test_exactly_one_agent_gets_the_ticket(self, responses: list[Response]) -> None:
        assert sorted(response.status_code for response in responses) == [200, 409, 409]

    def test_every_other_agent_is_told_the_ticket_was_taken(
        self, responses: list[Response]
    ) -> None:
        losers = [response for response in responses if response.status_code != 200]
        assert {response.json()["code"] for response in losers} == {"already_taken"}

    def test_the_ticket_ends_assigned_to_the_winner(
        self, responses: list[Response], session: Session, ticket_id: int
    ) -> None:
        (winner,) = [
            r.json()["assignee"]["id"] for r in responses if r.status_code == 200
        ]
        assert reload(session, ticket_id).assignee_id == winner

    def test_only_one_assignment_and_one_status_change_are_recorded(
        self, responses: list[Response], session: Session, ticket_id: int
    ) -> None:
        assert [row.kind for row in list_events(session, ticket_id)] == [
            EventKind.ASSIGNED,
            EventKind.STATUS_CHANGED,
        ]


@pytest.mark.usefixtures("demo_data")
class TestHoldAndResume:
    @pytest.fixture
    def ticket_id(self, act: Act, client: TestClient, login_as: LoginAs) -> int:
        """Prioridad alta creada el lunes 10:05, que vence el martes 10:05, y tomada por Elena."""
        created = post_ticket(client, login_as(REQUESTER_USERNAME), priority="high")
        ticket_id: int = created.json()["id"]
        act(AGENT_USERNAME, ticket_id, "take")
        return ticket_id

    def pause(
        self, act: Act, clock: FakeClock, ticket_id: int, duration: timedelta
    ) -> Response:
        act(AGENT_USERNAME, ticket_id, "hold")
        clock.advance(duration)
        return act(AGENT_USERNAME, ticket_id, "resume")

    @pytest.mark.parametrize("username", [AGENT_USERNAME, REQUESTER_USERNAME])
    def test_both_profiles_see_the_sla_paused_while_on_hold(
        self, act: Act, read: Read, ticket_id: int, username: str
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "hold")
        assert read(username, ticket_id).json()["sla"] == {
            "state": "paused",
            "due_at": None,
        }

    def test_holding_records_when_the_wait_began(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(HOUR)
        act(AGENT_USERNAME, ticket_id, "hold")
        assert reload(session, ticket_id).on_hold_since == clock.now()

    def test_holding_moves_the_ticket_to_on_hold(
        self, act: Act, ticket_id: int
    ) -> None:
        response = act(AGENT_USERNAME, ticket_id, "hold")
        assert response.json()["status"] == "on_hold"

    def test_resuming_returns_the_ticket_to_in_progress_with_its_agent(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        ticket = self.pause(act, clock, ticket_id, HOUR).json()
        assert (ticket["status"], ticket["assignee"]["id"]) == ("in_progress", AGENT_ID)

    def test_resuming_pushes_the_deadline_by_the_paused_business_time(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(HOUR)  # en espera de 11:05 a 15:05: 4 horas hábiles
        act(AGENT_USERNAME, ticket_id, "hold")
        clock.advance(4 * HOUR)
        response = act(AGENT_USERNAME, ticket_id, "resume")
        assert response.json()["sla"] == {
            "state": "on_track",
            "due_at": "2026-10-20T17:05:00Z",  # martes 14:05 local
        }

    def test_resuming_adds_the_paused_minutes_to_the_ticket(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        self.pause(act, clock, ticket_id, 4 * HOUR)
        assert reload(session, ticket_id).sla_paused_minutes == 240

    def test_resuming_clears_the_start_of_the_wait(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        self.pause(act, clock, ticket_id, HOUR)
        assert reload(session, ticket_id).on_hold_since is None

    def test_resuming_stores_the_new_deadline(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        self.pause(act, clock, ticket_id, 4 * HOUR)
        assert reload(session, ticket_id).sla_due_at == datetime(
            2026, 10, 20, 17, 5, tzinfo=UTC
        )

    def test_successive_pauses_accumulate(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        self.pause(act, clock, ticket_id, HOUR)  # 10:05 a 11:05
        clock.advance(HOUR)
        response = self.pause(act, clock, ticket_id, HOUR)  # 12:05 a 13:05
        assert (
            reload(session, ticket_id).sla_paused_minutes,
            response.json()["sla"]["due_at"],
        ) == (120, "2026-10-20T15:05:00Z")

    def test_only_business_time_counts_in_a_pause(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(7 * HOUR)  # lunes 17:05 local
        self.pause(act, clock, ticket_id, 17 * HOUR)  # hasta el martes 10:05
        assert reload(session, ticket_id).sla_paused_minutes == 55 + 65

    def test_a_wait_begun_before_the_deadline_counts_in_full(
        self, act: Act, client: TestClient, login_as: LoginAs, clock: FakeClock
    ) -> None:
        created = post_ticket(client, login_as(REQUESTER_USERNAME), priority="critical")
        critical_id = created.json()["id"]  # vence el lunes 14:05 local
        act(AGENT_USERNAME, critical_id, "take")
        clock.advance(timedelta(hours=3, minutes=30))  # 13:35, antes del vencimiento
        response = self.pause(act, clock, critical_id, 4 * HOUR)  # hasta las 17:35
        assert (
            response.json()["sla"]["due_at"] == "2026-10-20T12:05:00Z"
        )  # martes 09:05

    def test_a_wait_begun_after_the_deadline_does_not_move_it(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(25 * HOUR)  # martes 11:05 local, ya vencido
        response = self.pause(act, clock, ticket_id, 2 * HOUR)
        assert (
            reload(session, ticket_id).sla_paused_minutes,
            response.json()["sla"],
        ) == (0, {"state": "breached", "due_at": HIGH_DEADLINE})

    def test_a_ticket_held_after_its_deadline_stays_breached(
        self, act: Act, read: Read, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(25 * HOUR)
        act(AGENT_USERNAME, ticket_id, "hold")
        assert read(REQUESTER_USERNAME, ticket_id).json()["sla"] == {
            "state": "breached",
            "due_at": HIGH_DEADLINE,
        }

    def test_records_both_status_changes(
        self, act: Act, session: Session, clock: FakeClock, ticket_id: int
    ) -> None:
        self.pause(act, clock, ticket_id, HOUR)
        assert event_trail(session, ticket_id)[-2:] == [
            (EventKind.STATUS_CHANGED, AGENT_ID, "in_progress", "on_hold"),
            (EventKind.STATUS_CHANGED, AGENT_ID, "on_hold", "in_progress"),
        ]

    @pytest.mark.parametrize(
        ("action", "status", "label"),
        [
            ("hold", TicketStatus.IN_PROGRESS, "Dejar en espera"),
            ("resume", TicketStatus.ON_HOLD, "Retomar"),
            ("resolve", TicketStatus.IN_PROGRESS, "Resolver"),
        ],
    )
    def test_an_agent_who_is_not_assigned_cannot_move_the_ticket(
        self,
        act: Act,
        session: Session,
        action: str,
        status: TicketStatus,
        label: str,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        response = act(OTHER_AGENT_USERNAME, ticket_id, action)
        assert (response.status_code, response.json()) == (
            409,
            {
                "code": "action_not_allowed",
                "message": f"Solo el agente asignado al ticket puede realizar la acción «{label}».",
            },
        )


@pytest.mark.usefixtures("demo_data")
class TestResolve:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_id(
            session, status=TicketStatus.IN_PROGRESS, assignee_id=AGENT_ID
        )

    def test_the_ticket_is_resolved_at_the_current_instant(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(2 * HOUR)
        ticket = act(AGENT_USERNAME, ticket_id, "resolve").json()
        assert (ticket["status"], ticket["resolved_at"]) == (
            "resolved",
            "2026-10-19T15:05:00Z",
        )

    def test_resolving_within_the_deadline_meets_the_sla(
        self, act: Act, ticket_id: int
    ) -> None:
        response = act(AGENT_USERNAME, ticket_id, "resolve")
        assert response.json()["sla"] == {
            "state": "met",
            "due_at": "2026-10-20T13:05:00Z",
        }

    def test_resolving_after_the_deadline_misses_the_sla(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(2 * DAY)
        response = act(AGENT_USERNAME, ticket_id, "resolve")
        assert response.json()["sla"]["state"] == "missed"

    def test_records_the_status_change_attributed_to_the_agent(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "resolve")
        assert event_trail(session, ticket_id) == [
            (EventKind.STATUS_CHANGED, AGENT_ID, "in_progress", "resolved")
        ]

    def test_the_agent_can_only_comment_afterwards(
        self, act: Act, ticket_id: int
    ) -> None:
        response = act(AGENT_USERNAME, ticket_id, "resolve")
        assert response.json()["allowed_actions"] == ["comment"]

    def test_the_owner_is_offered_to_close_or_reopen_it(
        self, act: Act, read: Read, ticket_id: int
    ) -> None:
        act(AGENT_USERNAME, ticket_id, "resolve")
        assert read(REQUESTER_USERNAME, ticket_id).json()["allowed_actions"] == [
            "close",
            "reopen",
            "comment",
        ]


@pytest.mark.usefixtures("demo_data")
class TestClose:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_id(
            session,
            status=TicketStatus.RESOLVED,
            assignee_id=AGENT_ID,
            resolved_at=CREATED_AT + HOUR,
        )

    def test_the_owner_closes_the_ticket_at_the_current_instant(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(3 * HOUR)
        ticket = act(REQUESTER_USERNAME, ticket_id, "close").json()
        assert (ticket["status"], ticket["closed_at"]) == (
            "closed",
            "2026-10-19T16:05:00Z",
        )

    def test_closing_keeps_the_resolution_date_and_the_sla_outcome(
        self, act: Act, ticket_id: int
    ) -> None:
        ticket = act(REQUESTER_USERNAME, ticket_id, "close").json()
        assert (ticket["resolved_at"], ticket["sla"]["state"]) == (
            "2026-10-19T14:05:00Z",
            "met",
        )

    def test_a_closed_ticket_offers_no_actions(self, act: Act, ticket_id: int) -> None:
        response = act(REQUESTER_USERNAME, ticket_id, "close")
        assert response.json()["allowed_actions"] == []

    def test_records_the_status_change_attributed_to_the_requester(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(REQUESTER_USERNAME, ticket_id, "close")
        assert event_trail(session, ticket_id) == [
            (EventKind.STATUS_CHANGED, REQUESTER_ID, "resolved", "closed")
        ]

    def test_another_requester_does_not_see_the_ticket_to_close_it(
        self, act: Act, ticket_id: int
    ) -> None:
        response = act(OTHER_REQUESTER_USERNAME, ticket_id, "close")
        assert errors(response) == (404, "not_found")


@pytest.mark.usefixtures("demo_data")
class TestReopen:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_id(
            session,
            status=TicketStatus.RESOLVED,
            assignee_id=AGENT_ID,
            resolved_at=CREATED_AT + HOUR,
        )

    def test_the_ticket_returns_to_in_progress_with_its_agent(
        self, act: Act, ticket_id: int
    ) -> None:
        ticket = act(REQUESTER_USERNAME, ticket_id, "reopen").json()
        assert (ticket["status"], ticket["assignee"]["id"]) == ("in_progress", AGENT_ID)

    def test_the_resolution_date_is_cleared(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(REQUESTER_USERNAME, ticket_id, "reopen")
        assert reload(session, ticket_id).resolved_at is None

    def test_the_deadline_does_not_change(
        self, act: Act, read: Read, ticket_id: int
    ) -> None:
        before = read(REQUESTER_USERNAME, ticket_id).json()["sla"]["due_at"]
        reopened = act(REQUESTER_USERNAME, ticket_id, "reopen").json()
        assert reopened["sla"]["due_at"] == before

    def test_the_clock_keeps_running_after_the_deadline(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        clock.advance(2 * DAY)
        reopened = act(REQUESTER_USERNAME, ticket_id, "reopen").json()
        assert reopened["sla"]["state"] == "breached"

    def test_records_the_status_change_attributed_to_the_requester(
        self, act: Act, session: Session, ticket_id: int
    ) -> None:
        act(REQUESTER_USERNAME, ticket_id, "reopen")
        assert event_trail(session, ticket_id) == [
            (EventKind.STATUS_CHANGED, REQUESTER_ID, "resolved", "in_progress")
        ]

    def test_the_agent_can_resolve_it_again(
        self, act: Act, clock: FakeClock, ticket_id: int
    ) -> None:
        act(REQUESTER_USERNAME, ticket_id, "reopen")
        clock.advance(2 * HOUR)
        again = act(AGENT_USERNAME, ticket_id, "resolve").json()
        assert (again["status"], again["resolved_at"]) == (
            "resolved",
            "2026-10-19T15:05:00Z",
        )


# Cada fila de la tabla de ADL-008 pedida desde cada estado que no es su origen,
# y por quien la tabla autoriza: el rol es el correcto, el estado no.
# Con `add_ticket_in`, el asignado de los estados con dueño es AGENT_ID, el mismo agente que
# pide «tomar»: por eso esa fila es `action_not_allowed` y no `already_taken`.
WRONG_STATE_REQUESTS = [
    pytest.param(
        transition.action.value,
        USERNAME_BY_ROLE[transition.role],
        status,
        id=f"{transition.action}-from-{status}",
    )
    for transition in TRANSITIONS
    for status in TicketStatus
    if status != transition.source
]
# Cada fila pedida desde su estado de origen por el rol opuesto: el estado es el correcto, el rol no.
WRONG_ROLE_REQUESTS = [
    pytest.param(
        transition.action.value,
        OTHER_USERNAME_BY_ROLE[transition.role],
        transition.source,
        id=f"{transition.action}-by-{OTHER_USERNAME_BY_ROLE[transition.role]}",
    )
    for transition in TRANSITIONS
]


@pytest.mark.usefixtures("demo_data")
class TestTransitionRules:
    @pytest.mark.parametrize(("action", "username", "status"), WRONG_STATE_REQUESTS)
    def test_an_action_in_the_wrong_status_is_not_allowed(
        self,
        act: Act,
        session: Session,
        action: str,
        username: str,
        status: TicketStatus,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert errors(act(username, ticket_id, action)) == (409, "action_not_allowed")

    @pytest.mark.parametrize(("action", "username", "status"), WRONG_ROLE_REQUESTS)
    def test_an_action_of_the_other_profile_is_forbidden(
        self,
        act: Act,
        session: Session,
        action: str,
        username: str,
        status: TicketStatus,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert errors(act(username, ticket_id, action)) == (403, "forbidden")

    def test_the_rejection_explains_the_current_status(
        self, act: Act, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        response = act(AGENT_USERNAME, ticket_id, "hold")
        assert response.json()["message"] == (
            "La acción «Dejar en espera» no está disponible con el ticket en estado «Abierto»."
        )

    def test_a_rejected_action_changes_nothing(
        self, act: Act, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        act(AGENT_USERNAME, ticket_id, "resolve")
        ticket = reload(session, ticket_id)
        assert (
            ticket.status,
            ticket.resolved_at,
            ticket.assignee_id,
            list_events(session, ticket_id),
        ) == (TicketStatus.OPEN, None, None, [])

    def test_an_unknown_ticket_answers_404(self, act: Act) -> None:
        assert errors(act(AGENT_USERNAME, 999, "take")) == (404, "not_found")


ALLOWED_ACTIONS = [
    (TicketStatus.OPEN, AGENT_USERNAME, ["take", "comment", "change_priority"]),
    (TicketStatus.OPEN, OTHER_AGENT_USERNAME, ["take", "comment", "change_priority"]),
    (TicketStatus.OPEN, REQUESTER_USERNAME, ["cancel", "comment"]),
    (
        TicketStatus.IN_PROGRESS,
        AGENT_USERNAME,
        ["hold", "resolve", "comment", "change_priority"],
    ),
    (TicketStatus.IN_PROGRESS, OTHER_AGENT_USERNAME, ["comment", "change_priority"]),
    (TicketStatus.IN_PROGRESS, REQUESTER_USERNAME, ["comment"]),
    (TicketStatus.ON_HOLD, AGENT_USERNAME, ["resume", "comment", "change_priority"]),
    (TicketStatus.ON_HOLD, OTHER_AGENT_USERNAME, ["comment", "change_priority"]),
    (TicketStatus.ON_HOLD, REQUESTER_USERNAME, ["comment"]),
    (TicketStatus.RESOLVED, AGENT_USERNAME, ["comment"]),
    (TicketStatus.RESOLVED, OTHER_AGENT_USERNAME, ["comment"]),
    (TicketStatus.RESOLVED, REQUESTER_USERNAME, ["close", "reopen", "comment"]),
    (TicketStatus.CLOSED, AGENT_USERNAME, []),
    (TicketStatus.CLOSED, OTHER_AGENT_USERNAME, []),
    (TicketStatus.CLOSED, REQUESTER_USERNAME, []),
    (TicketStatus.CANCELLED, AGENT_USERNAME, []),
    (TicketStatus.CANCELLED, OTHER_AGENT_USERNAME, []),
    (TicketStatus.CANCELLED, REQUESTER_USERNAME, []),
]


@pytest.mark.usefixtures("demo_data")
class TestAllowedActions:
    """Elena es la agente asignada, Felipe otro agente y Ana la solicitante dueña."""

    @pytest.mark.parametrize(("status", "username", "expected"), ALLOWED_ACTIONS)
    def test_depend_on_the_status_and_on_who_asks(
        self,
        read: Read,
        session: Session,
        status: TicketStatus,
        username: str,
        expected: list[str],
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert read(username, ticket_id).json()["allowed_actions"] == expected


@pytest.mark.usefixtures("demo_data")
class TestFullLifecycle:
    def test_a_ticket_goes_from_creation_to_closing_leaving_its_trail(
        self,
        act: Act,
        client: TestClient,
        login_as: LoginAs,
        session: Session,
        clock: FakeClock,
    ) -> None:
        created = post_ticket(client, login_as(REQUESTER_USERNAME))
        ticket_id: int = created.json()["id"]
        for username, action in (
            (AGENT_USERNAME, "take"),
            (AGENT_USERNAME, "hold"),
            (AGENT_USERNAME, "resume"),
            (AGENT_USERNAME, "resolve"),
            (REQUESTER_USERNAME, "close"),
        ):
            clock.advance(HOUR)
            assert act(username, ticket_id, action).status_code == 200
        assert event_trail(session, ticket_id) == [
            (EventKind.CREATED, REQUESTER_ID, None, "open"),
            (EventKind.ASSIGNED, AGENT_ID, None, "Elena Vidal"),
            (EventKind.STATUS_CHANGED, AGENT_ID, "open", "in_progress"),
            (EventKind.STATUS_CHANGED, AGENT_ID, "in_progress", "on_hold"),
            (EventKind.STATUS_CHANGED, AGENT_ID, "on_hold", "in_progress"),
            (EventKind.STATUS_CHANGED, AGENT_ID, "in_progress", "resolved"),
            (EventKind.STATUS_CHANGED, REQUESTER_ID, "resolved", "closed"),
        ]
