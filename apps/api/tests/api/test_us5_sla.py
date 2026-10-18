from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import list_events
from droidesk_api.tickets.enums import TicketStatus
from tests.api.helpers import (
    NOT_FOUND,
    TICKETS_URL,
    Act,
    LoginAs,
    PatchTicket,
    Read,
    add_ticket_in_id,
    post_ticket,
    reload,
)
from tests.factories import (
    AGENT_USERNAME,
    OTHER_AGENT_ID,
    OTHER_AGENT_USERNAME,
    OTHER_REQUESTER_USERNAME,
    REQUESTER_ID,
    REQUESTER_USERNAME,
)
from tests.fakes import FakeClock

SANTIAGO = ZoneInfo("America/Santiago")
# Octubre de 2026 ya está en horario de verano y no cambia hasta abril, así que la jornada
# de 09:00 a 18:00 local es la misma toda la semana. El lunes 19 es el día de los ejemplos.
OCTOBER_DAYS = {
    "mon": 19,
    "tue": 20,
    "wed": 21,
    "thu": 22,
    "fri": 23,
    "sat": 24,
    "next_mon": 26,
    "next_tue": 27,
}
FORBIDDEN_MESSAGE = "Tu perfil no puede realizar la acción «Cambiar prioridad»."


def local(day: str, hour: int, minute: int = 0) -> datetime:
    """Un instante de la semana de los ejemplos, dicho en la hora de la organización."""
    local_time = datetime(2026, 10, OCTOBER_DAYS[day], hour, minute, tzinfo=SANTIAGO)
    return local_time.astimezone(UTC)


def utc_iso(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def sla_dict(state: str | None, due_at: datetime | None) -> dict[str, Any]:
    return {"state": state, "due_at": None if due_at is None else utc_iso(due_at)}


def errors(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


def trail(session: Session, ticket_id: int) -> list[tuple[EventKind, int, str | None]]:
    """Tipo, autor y valor nuevo de cada evento del ticket, en orden."""
    return [
        (row.kind, row.actor_id, row.to_value)
        for row in list_events(session, ticket_id)
    ]


CreateAt = Callable[..., dict[str, Any]]
SlaAt = Callable[[int, datetime], dict[str, Any]]
WaitBetween = Callable[[int, datetime, datetime], Response]


@pytest.fixture
def create_at(client: TestClient, login_as: LoginAs, clock: FakeClock) -> CreateAt:
    """Ana crea un ticket en el instante dado y recibe el detalle que responde la API."""

    def create(instant: datetime, priority: str, **overrides: Any) -> dict[str, Any]:
        clock.set(instant)
        created = post_ticket(
            client, login_as(REQUESTER_USERNAME), priority=priority, **overrides
        )
        assert created.status_code == 201
        ticket: dict[str, Any] = created.json()
        return ticket

    return create


@pytest.fixture
def sla_at(read: Read, clock: FakeClock) -> SlaAt:
    """El SLA que ve el solicitante en el instante dado."""

    def sla_in(ticket_id: int, instant: datetime) -> dict[str, Any]:
        clock.set(instant)
        sla: dict[str, Any] = read(REQUESTER_USERNAME, ticket_id).json()["sla"]
        return sla

    return sla_in


@pytest.fixture
def wait_between(act: Act, clock: FakeClock) -> WaitBetween:
    """Elena deja el ticket en espera al inicio y lo retoma al final; devuelve la respuesta de retomar."""

    def wait(ticket_id: int, start: datetime, end: datetime) -> Response:
        clock.set(start)
        act(AGENT_USERNAME, ticket_id, "hold")
        clock.set(end)
        return act(AGENT_USERNAME, ticket_id, "resume")

    return wait


@pytest.fixture
def high_ticket(create_at: CreateAt, act: Act, clock: FakeClock) -> int:
    """Alta creada el lunes a las 10:00, que vence el martes a las 10:00, y tomada por Elena."""
    ticket_id: int = create_at(local("mon", 10), "high")["id"]
    clock.set(local("mon", 10, 30))
    act(AGENT_USERNAME, ticket_id, "take")
    return ticket_id


# Los ejemplos de creación de «Bordes del SLA» del quickstart: prioridad, creación y vencimiento.
CREATION_CASES = [
    pytest.param(
        "high", local("mon", 10), local("tue", 10), id="high-within-the-workday"
    ),
    pytest.param(
        "high", local("fri", 20), local("next_mon", 18), id="high-after-hours"
    ),
    pytest.param(
        "critical",
        local("mon", 16),
        local("tue", 11),
        id="critical-across-the-closing",
    ),
    pytest.param(
        "medium",
        local("thu", 12),
        local("next_tue", 12),
        id="medium-across-the-weekend",
    ),
    pytest.param(
        "low", local("mon", 9), local("fri", 18), id="low-takes-45-business-hours"
    ),
]


@pytest.mark.usefixtures("demo_data")
class TestDeadlineAtCreation:
    """Los ejemplos de creación del quickstart, a través de la API."""

    @pytest.mark.parametrize(("priority", "created", "due"), CREATION_CASES)
    def test_the_deadline_counts_only_business_time(
        self, create_at: CreateAt, priority: str, created: datetime, due: datetime
    ) -> None:
        ticket = create_at(created, priority)
        assert ticket["sla"] == sla_dict("on_track", due)

    @pytest.mark.parametrize(("priority", "created", "due"), CREATION_CASES)
    @pytest.mark.parametrize("username", [REQUESTER_USERNAME, AGENT_USERNAME])
    def test_both_profiles_read_the_same_commitment(
        self,
        create_at: CreateAt,
        read: Read,
        username: str,
        priority: str,
        created: datetime,
        due: datetime,
    ) -> None:
        ticket_id = create_at(created, priority)["id"]
        assert read(username, ticket_id).json()["sla"] == sla_dict("on_track", due)

    def test_a_ticket_created_on_a_saturday_starts_counting_on_monday(
        self, create_at: CreateAt
    ) -> None:
        ticket = create_at(local("sat", 11), "critical")
        assert ticket["sla"]["due_at"] == utc_iso(local("next_mon", 13))


@pytest.mark.usefixtures("demo_data")
class TestPause:
    def test_a_wait_inside_the_deadline_pushes_it_by_the_time_waited(
        self, wait_between: WaitBetween, high_ticket: int
    ) -> None:
        resumed = wait_between(high_ticket, local("mon", 11), local("mon", 15))
        assert resumed.json()["sla"] == sla_dict("on_track", local("tue", 14))

    def test_the_sla_is_paused_while_the_ticket_waits(
        self, act: Act, sla_at: SlaAt, clock: FakeClock, high_ticket: int
    ) -> None:
        clock.set(local("mon", 11))
        act(AGENT_USERNAME, high_ticket, "hold")
        assert sla_at(high_ticket, local("mon", 13)) == sla_dict("paused", None)

    def test_a_wait_that_begins_after_the_deadline_leaves_the_ticket_breached(
        self, act: Act, sla_at: SlaAt, clock: FakeClock, high_ticket: int
    ) -> None:
        clock.set(local("tue", 11))  # vencido desde las 10:00
        act(AGENT_USERNAME, high_ticket, "hold")
        assert sla_at(high_ticket, local("tue", 12)) == sla_dict(
            "breached", local("tue", 10)
        )

    def test_resuming_after_a_late_wait_does_not_move_the_deadline(
        self, wait_between: WaitBetween, high_ticket: int
    ) -> None:
        resumed = wait_between(high_ticket, local("tue", 11), local("tue", 13))
        assert resumed.json()["sla"] == sla_dict("breached", local("tue", 10))


@pytest.mark.usefixtures("demo_data")
class TestAtRisk:
    """Una Alta son 9 horas hábiles: «Por vencer» cuando quedan menos de 2 h 15 min."""

    @pytest.mark.parametrize(
        ("instant", "state"),
        [
            pytest.param(local("mon", 10, 1), "on_track", id="just-created"),
            pytest.param(
                local("mon", 16, 45), "on_track", id="exactly-135-minutes-left"
            ),
            pytest.param(local("mon", 16, 46), "at_risk", id="134-minutes-left"),
            pytest.param(local("tue", 9, 59), "at_risk", id="one-minute-left"),
            pytest.param(local("tue", 10), "breached", id="at-the-deadline"),
        ],
    )
    def test_the_state_changes_as_the_deadline_approaches(
        self, create_at: CreateAt, sla_at: SlaAt, instant: datetime, state: str
    ) -> None:
        ticket_id = create_at(local("mon", 10), "high")["id"]
        assert sla_at(ticket_id, instant) == sla_dict(state, local("tue", 10))


@pytest.mark.usefixtures("demo_data")
class TestOutcome:
    """Resuelto antes o justo en el vencimiento cumple el SLA; después, lo incumple."""

    @pytest.mark.parametrize(
        ("resolved", "state"),
        [
            pytest.param(local("tue", 9, 59), "met", id="a-minute-early"),
            pytest.param(local("tue", 10), "met", id="exactly-at-the-deadline"),
            pytest.param(local("tue", 10, 1), "missed", id="a-minute-late"),
        ],
    )
    def test_the_outcome_depends_on_when_it_was_resolved(
        self,
        act: Act,
        clock: FakeClock,
        high_ticket: int,
        resolved: datetime,
        state: str,
    ) -> None:
        clock.set(resolved)
        ticket = act(AGENT_USERNAME, high_ticket, "resolve").json()
        assert ticket["sla"] == sla_dict(state, local("tue", 10))

    @pytest.mark.parametrize(
        ("resolved", "state"),
        [(local("mon", 12), "met"), (local("tue", 12), "missed")],
    )
    def test_the_outcome_does_not_change_as_time_passes(
        self,
        act: Act,
        sla_at: SlaAt,
        clock: FakeClock,
        high_ticket: int,
        resolved: datetime,
        state: str,
    ) -> None:
        clock.set(resolved)
        act(AGENT_USERNAME, high_ticket, "resolve")
        later = resolved + timedelta(days=30)
        assert sla_at(high_ticket, later)["state"] == state

    def test_a_cancelled_ticket_has_no_sla_state(
        self, create_at: CreateAt, act: Act, sla_at: SlaAt
    ) -> None:
        ticket_id = create_at(local("mon", 10), "high")["id"]
        act(REQUESTER_USERNAME, ticket_id, "cancel")
        assert sla_at(ticket_id, local("tue", 12)) == sla_dict(None, None)


@pytest.mark.usefixtures("demo_data")
class TestChangePriority:
    @pytest.fixture
    def critical_id(self, create_at: CreateAt) -> int:
        """Crítica creada el lunes a las 10:05, que vence ese día a las 14:05."""
        ticket: dict[str, Any] = create_at(local("mon", 10, 5), "critical")
        return int(ticket["id"])

    def test_lowering_it_recalculates_the_deadline_from_the_creation(
        self,
        patch_ticket: PatchTicket,
        clock: FakeClock,
        critical_id: int,
    ) -> None:
        clock.set(
            local("tue", 15)
        )  # el cálculo parte de la creación, no de este momento
        response = patch_ticket(AGENT_USERNAME, critical_id, {"priority": "low"})
        assert response.json()["sla"] == sla_dict("on_track", local("next_mon", 10, 5))

    def test_raising_it_can_leave_the_ticket_already_breached(
        self, create_at: CreateAt, patch_ticket: PatchTicket, clock: FakeClock
    ) -> None:
        low_id = create_at(local("mon", 10, 5), "low")["id"]
        clock.set(local("mon", 15))
        response = patch_ticket(AGENT_USERNAME, low_id, {"priority": "critical"})
        assert response.json()["sla"] == sla_dict("breached", local("mon", 14, 5))

    def test_the_new_priority_and_deadline_are_stored(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        critical_id: int,
    ) -> None:
        patch_ticket(AGENT_USERNAME, critical_id, {"priority": "low"})
        ticket = reload(session, critical_id)
        assert (ticket.priority, ticket.sla_due_at) == (
            "low",
            local("next_mon", 10, 5),
        )

    def test_the_response_is_the_updated_detail(
        self, patch_ticket: PatchTicket, critical_id: int
    ) -> None:
        ticket = patch_ticket(AGENT_USERNAME, critical_id, {"priority": "high"}).json()
        assert (ticket["id"], ticket["priority"], ticket["allowed_actions"]) == (
            critical_id,
            "high",
            ["take", "comment", "change_priority"],
        )

    def test_the_wait_time_already_accumulated_still_counts(
        self,
        create_at: CreateAt,
        act: Act,
        wait_between: WaitBetween,
        patch_ticket: PatchTicket,
        session: Session,
        clock: FakeClock,
    ) -> None:
        ticket_id = create_at(local("mon", 10, 5), "high")["id"]
        act(AGENT_USERNAME, ticket_id, "take")
        wait_between(ticket_id, local("mon", 11, 5), local("mon", 15, 5))  # 4 h hábiles
        clock.set(local("mon", 15, 30))
        response = patch_ticket(AGENT_USERNAME, ticket_id, {"priority": "critical"})
        # El plazo de Crítica (4 h) más las 4 h de espera: 8 h hábiles desde la creación.
        assert (
            response.json()["sla"],
            reload(session, ticket_id).sla_paused_minutes,
        ) == (sla_dict("on_track", local("tue", 9, 5)), 240)

    def test_a_priority_changed_during_the_wait_is_resumed_with_the_new_term(
        self,
        create_at: CreateAt,
        act: Act,
        patch_ticket: PatchTicket,
        clock: FakeClock,
    ) -> None:
        ticket_id = create_at(local("mon", 10, 5), "high")["id"]
        act(AGENT_USERNAME, ticket_id, "take")
        clock.set(local("mon", 11, 5))
        act(AGENT_USERNAME, ticket_id, "hold")
        clock.set(local("mon", 12, 5))
        patch_ticket(AGENT_USERNAME, ticket_id, {"priority": "low"})
        clock.set(local("mon", 15, 5))  # 4 h hábiles en espera
        resumed = act(AGENT_USERNAME, ticket_id, "resume")
        assert resumed.json()["sla"] == sla_dict("on_track", local("next_mon", 14, 5))

    def test_going_back_to_the_previous_priority_restores_the_deadline(
        self, create_at: CreateAt, patch_ticket: PatchTicket
    ) -> None:
        ticket_id = create_at(local("mon", 10, 5), "high")["id"]
        patch_ticket(AGENT_USERNAME, ticket_id, {"priority": "low"})
        back = patch_ticket(AGENT_USERNAME, ticket_id, {"priority": "high"})
        assert back.json()["sla"]["due_at"] == utc_iso(local("tue", 10, 5))

    def test_a_ticket_on_hold_stays_paused(
        self, patch_ticket: PatchTicket, session: Session
    ) -> None:
        held_id = add_ticket_in_id(session, TicketStatus.ON_HOLD)
        response = patch_ticket(AGENT_USERNAME, held_id, {"priority": "critical"})
        assert response.json()["sla"] == sla_dict("paused", None)

    @pytest.mark.parametrize(
        "status",
        [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD],
    )
    @pytest.mark.parametrize("username", [AGENT_USERNAME, OTHER_AGENT_USERNAME])
    def test_any_agent_can_adjust_a_ticket_that_is_not_resolved(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        status: TicketStatus,
        username: str,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        response = patch_ticket(username, ticket_id, {"priority": "critical"})
        assert (response.status_code, response.json()["priority"]) == (200, "critical")

    def test_records_the_previous_and_the_new_priority_under_the_agent(
        self, patch_ticket: PatchTicket, session: Session, critical_id: int
    ) -> None:
        patch_ticket(OTHER_AGENT_USERNAME, critical_id, {"priority": "low"})
        last = list_events(session, critical_id)[-1]
        assert (last.kind, last.actor_id, last.from_value, last.to_value) == (
            EventKind.PRIORITY_CHANGED,
            OTHER_AGENT_ID,
            "critical",
            "low",
        )

    def test_the_event_is_dated_at_the_moment_of_the_change(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        clock: FakeClock,
        critical_id: int,
    ) -> None:
        clock.set(local("mon", 12))
        patch_ticket(AGENT_USERNAME, critical_id, {"priority": "low"})
        assert list_events(session, critical_id)[-1].created_at == local("mon", 12)

    def test_the_history_in_the_response_shows_the_change_last(
        self, patch_ticket: PatchTicket, critical_id: int
    ) -> None:
        history = patch_ticket(AGENT_USERNAME, critical_id, {"priority": "low"}).json()[
            "history"
        ]
        assert [(e["kind"], e["from_value"], e["to_value"]) for e in history] == [
            ("created", None, "open"),
            ("priority_changed", "critical", "low"),
        ]

    def test_the_update_time_is_the_moment_of_the_change(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        clock: FakeClock,
        critical_id: int,
    ) -> None:
        clock.set(local("mon", 12))
        patch_ticket(AGENT_USERNAME, critical_id, {"priority": "low"})
        assert reload(session, critical_id).updated_at == local("mon", 12)

    def test_asking_for_the_current_priority_answers_the_ticket_without_changes(
        self, patch_ticket: PatchTicket, read: Read, critical_id: int
    ) -> None:
        before = read(AGENT_USERNAME, critical_id).json()
        response = patch_ticket(AGENT_USERNAME, critical_id, {"priority": "critical"})
        assert (response.status_code, response.json()) == (200, before)

    def test_asking_for_the_current_priority_leaves_no_event_and_no_new_date(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        clock: FakeClock,
        critical_id: int,
    ) -> None:
        clock.set(local("mon", 12))
        patch_ticket(AGENT_USERNAME, critical_id, {"priority": "critical"})
        assert (
            trail(session, critical_id),
            reload(session, critical_id).updated_at,
        ) == ([(EventKind.CREATED, REQUESTER_ID, "open")], local("mon", 10, 5))


@pytest.mark.usefixtures("demo_data")
class TestChangePriorityRejections:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_in_id(session, TicketStatus.IN_PROGRESS, priority="high")

    def assert_untouched(self, session: Session, ticket_id: int) -> None:
        ticket = reload(session, ticket_id)
        assert (ticket.priority, list_events(session, ticket_id)) == ("high", [])

    def test_the_requester_is_forbidden_even_on_their_own_ticket(
        self, patch_ticket: PatchTicket, ticket_id: int
    ) -> None:
        response = patch_ticket(REQUESTER_USERNAME, ticket_id, {"priority": "low"})
        assert (response.status_code, response.json()) == (
            403,
            {"code": "forbidden", "message": FORBIDDEN_MESSAGE},
        )

    def test_a_forbidden_request_changes_nothing(
        self, patch_ticket: PatchTicket, session: Session, ticket_id: int
    ) -> None:
        patch_ticket(REQUESTER_USERNAME, ticket_id, {"priority": "low"})
        self.assert_untouched(session, ticket_id)

    def test_a_requester_cannot_tell_that_another_ticket_exists(
        self, patch_ticket: PatchTicket, ticket_id: int
    ) -> None:
        response = patch_ticket(
            OTHER_REQUESTER_USERNAME, ticket_id, {"priority": "low"}
        )
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    @pytest.mark.parametrize("username", [AGENT_USERNAME, REQUESTER_USERNAME])
    def test_an_unknown_ticket_answers_404(
        self, patch_ticket: PatchTicket, username: str
    ) -> None:
        response = patch_ticket(username, 999, {"priority": "low"})
        assert errors(response) == (404, "not_found")

    @pytest.mark.parametrize(
        ("status", "label"),
        [
            (TicketStatus.RESOLVED, "Resuelto"),
            (TicketStatus.CLOSED, "Cerrado"),
            (TicketStatus.CANCELLED, "Cancelado"),
        ],
    )
    def test_a_resolved_or_final_ticket_is_not_allowed(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        status: TicketStatus,
        label: str,
    ) -> None:
        closed_id = add_ticket_in_id(session, status, priority="high")
        response = patch_ticket(AGENT_USERNAME, closed_id, {"priority": "low"})
        assert (response.status_code, response.json()) == (
            409,
            {
                "code": "action_not_allowed",
                "message": f"La acción «Cambiar prioridad» no está disponible con el ticket en estado «{label}».",
            },
        )

    @pytest.mark.parametrize(
        "status", [TicketStatus.RESOLVED, TicketStatus.CLOSED, TicketStatus.CANCELLED]
    )
    def test_a_rejected_adjustment_changes_nothing(
        self, patch_ticket: PatchTicket, session: Session, status: TicketStatus
    ) -> None:
        closed_id = add_ticket_in_id(session, status, priority="high")
        before = reload(session, closed_id).sla_due_at
        patch_ticket(AGENT_USERNAME, closed_id, {"priority": "low"})
        ticket = reload(session, closed_id)
        assert (
            ticket.priority,
            ticket.sla_due_at,
            list_events(session, closed_id),
        ) == (
            "high",
            before,
            [],
        )

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"priority": "urgent"}, id="unknown-priority"),
            pytest.param({"priority": "HIGH"}, id="wrong-case"),
            pytest.param({"priority": None}, id="null-priority"),
            pytest.param({"priority": 2}, id="number"),
            pytest.param({}, id="no-priority"),
        ],
    )
    def test_an_invalid_priority_answers_422_and_changes_nothing(
        self,
        patch_ticket: PatchTicket,
        session: Session,
        ticket_id: int,
        body: dict[str, Any],
    ) -> None:
        response = patch_ticket(AGENT_USERNAME, ticket_id, body)
        ticket = reload(session, ticket_id)
        assert (
            response.status_code,
            ticket.priority,
            list_events(session, ticket_id),
        ) == (422, "high", [])

    @pytest.mark.parametrize("bad_id", [0, -1, 2**63])
    def test_an_id_outside_the_valid_range_answers_422(
        self, patch_ticket: PatchTicket, bad_id: int
    ) -> None:
        response = patch_ticket(AGENT_USERNAME, bad_id, {"priority": "low"})
        assert response.status_code == 422

    def test_without_a_session_answers_401(
        self, client: TestClient, ticket_id: int
    ) -> None:
        response = client.patch(f"{TICKETS_URL}/{ticket_id}", json={"priority": "low"})
        assert errors(response) == (401, "not_authenticated")


@pytest.mark.usefixtures("demo_data")
class TestQueueByUrgency:
    """La cola con prioridades reales, creadas a través de la API en el mismo instante."""

    @pytest.fixture
    def queue_titles(
        self, client: TestClient, login_as: LoginAs
    ) -> Callable[[], list[str]]:
        def titles() -> list[str]:
            queue = client.get(
                TICKETS_URL, params={"view": "queue"}, headers=login_as(AGENT_USERNAME)
            )
            return [ticket["title"] for ticket in queue.json()]

        return titles

    @pytest.fixture
    def tickets(self, create_at: CreateAt) -> dict[str, int]:
        """Creados de la menos a la más urgente, para que el orden de la cola no sea el de llegada."""
        return {
            priority: create_at(local("mon", 10), priority, title=priority)["id"]
            for priority in ("low", "medium", "high", "critical")
        }

    def test_the_most_urgent_priority_comes_first(
        self, tickets: dict[str, int], queue_titles: Callable[[], list[str]]
    ) -> None:
        assert queue_titles() == ["critical", "high", "medium", "low"]

    def test_a_ticket_on_hold_goes_last_even_with_the_closest_deadline(
        self,
        tickets: dict[str, int],
        act: Act,
        clock: FakeClock,
        queue_titles: Callable[[], list[str]],
    ) -> None:
        clock.set(local("mon", 11))
        act(AGENT_USERNAME, tickets["critical"], "take")
        act(AGENT_USERNAME, tickets["critical"], "hold")
        assert queue_titles() == ["high", "medium", "low", "critical"]

    def test_the_ticket_returns_to_its_place_when_it_resumes(
        self,
        tickets: dict[str, int],
        act: Act,
        wait_between: WaitBetween,
        clock: FakeClock,
        queue_titles: Callable[[], list[str]],
    ) -> None:
        clock.set(local("mon", 10, 30))
        act(AGENT_USERNAME, tickets["critical"], "take")
        wait_between(tickets["critical"], local("mon", 11), local("mon", 12))
        assert queue_titles() == ["critical", "high", "medium", "low"]

    def test_lowering_the_priority_moves_the_ticket_down_the_queue(
        self,
        tickets: dict[str, int],
        patch_ticket: PatchTicket,
        queue_titles: Callable[[], list[str]],
    ) -> None:
        patch_ticket(AGENT_USERNAME, tickets["critical"], {"priority": "low"})
        # Igual vencimiento que el otro Baja: el más antiguo (menor id) va primero.
        assert queue_titles() == ["high", "medium", "low", "critical"]

    def test_raising_the_priority_moves_the_ticket_up_the_queue(
        self,
        tickets: dict[str, int],
        patch_ticket: PatchTicket,
        queue_titles: Callable[[], list[str]],
    ) -> None:
        patch_ticket(AGENT_USERNAME, tickets["low"], {"priority": "critical"})
        assert queue_titles() == ["low", "critical", "high", "medium"]
