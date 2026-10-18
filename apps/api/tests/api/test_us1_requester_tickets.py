from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import list_events
from droidesk_api.core.db import persisted_id
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.models import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH, Ticket
from tests.factories import (
    AGENT_ID,
    AGENT_USERNAME,
    CREATED_AT,
    OTHER_REQUESTER_ID,
    REQUESTER_ID,
    REQUESTER_USERNAME,
    add_ticket,
)
from tests.fakes import FakeClock

LoginAs = Callable[[str], dict[str, str]]
TICKETS_URL = "/api/v1/tickets"
NEW_TICKET = {
    "title": "No puedo entrar a la VPN",
    "description": "Desde esta mañana la VPN rechaza mis credenciales.",
    "category_id": 4,
}
NOT_FOUND = {"code": "not_found", "message": "El ticket no existe."}
SANTIAGO_FRIDAY_EVENING = datetime(2026, 10, 23, 23, 0, tzinfo=UTC)  # 20:00 local


def add_ticket_id(session: Session, **overrides: Any) -> int:
    return persisted_id(add_ticket(session, **overrides))


def reload(session: Session, ticket_id: int) -> Ticket:
    """Lee el ticket tal como lo dejó la API, que usa otra sesión."""
    session.expire_all()
    return session.get_one(Ticket, ticket_id)


def transitions_url(ticket_id: int) -> str:
    return f"{TICKETS_URL}/{ticket_id}/transitions"


def post_ticket(
    client: TestClient, headers: dict[str, str], **overrides: Any
) -> Response:
    return client.post(TICKETS_URL, headers=headers, json=NEW_TICKET | overrides)


def invalid_field(response: Response) -> list[str | int]:
    assert response.status_code == 422
    location: list[str | int] = response.json()["detail"][0]["loc"]
    return location


@pytest.mark.usefixtures("demo_data")
class TestCreation:
    @pytest.fixture
    def created(self, client: TestClient, login_as: LoginAs) -> Response:
        return post_ticket(client, login_as(REQUESTER_USERNAME))

    def test_answers_201(self, created: Response) -> None:
        assert created.status_code == 201

    def test_the_ticket_starts_open_and_unassigned(self, created: Response) -> None:
        ticket = created.json()
        assert (ticket["status"], ticket["assignee"]) == ("open", None)

    def test_the_ticket_belongs_to_its_creator(self, created: Response) -> None:
        assert created.json()["requester"] == {"id": REQUESTER_ID, "name": "Ana Rojas"}

    def test_keeps_the_title_description_and_category(self, created: Response) -> None:
        ticket = created.json()
        assert (ticket["title"], ticket["description"], ticket["category"]) == (
            NEW_TICKET["title"],
            NEW_TICKET["description"],
            {"id": 4, "name": "Red y conectividad"},
        )

    def test_is_created_at_the_current_instant(self, created: Response) -> None:
        assert created.json()["created_at"] == "2026-10-19T13:05:00Z"

    def test_starts_without_resolution_closing_or_cancellation(
        self, created: Response
    ) -> None:
        ticket = created.json()
        assert (
            ticket["resolved_at"],
            ticket["closed_at"],
            ticket["cancelled_at"],
        ) == (None, None, None)

    def test_the_requester_may_cancel_or_comment(self, created: Response) -> None:
        assert created.json()["allowed_actions"] == ["cancel", "comment"]

    def test_the_sla_starts_on_track(self, created: Response) -> None:
        assert created.json()["sla"]["state"] == "on_track"

    def test_priority_is_medium_by_default(self, created: Response) -> None:
        assert created.json()["priority"] == "medium"

    def test_the_ticket_is_stored_open(
        self, created: Response, session: Session
    ) -> None:
        stored = session.get_one(Ticket, created.json()["id"])
        assert (stored.status, stored.requester_id) == (
            TicketStatus.OPEN,
            REQUESTER_ID,
        )

    def test_records_the_created_event(
        self, created: Response, session: Session
    ) -> None:
        (event,) = list_events(session, created.json()["id"])
        assert (event.kind, event.actor_id, event.from_value, event.to_value) == (
            EventKind.CREATED,
            REQUESTER_ID,
            None,
            "open",
        )

    def test_the_created_event_carries_the_creation_instant(
        self, created: Response, session: Session
    ) -> None:
        (event,) = list_events(session, created.json()["id"])
        assert event.created_at == CREATED_AT

    @pytest.mark.parametrize(
        ("priority", "due_at"),
        [
            ("critical", "2026-10-19T17:05:00Z"),  # 4 h hábiles: lunes 14:05 local
            ("high", "2026-10-20T13:05:00Z"),  # 1 día hábil: martes 10:05 local
            ("medium", "2026-10-22T13:05:00Z"),  # 3 días hábiles: jueves 10:05 local
            ("low", "2026-10-26T13:05:00Z"),  # 5 días hábiles: lunes 10:05 local
        ],
    )
    def test_each_priority_sets_its_business_time_deadline(
        self, client: TestClient, login_as: LoginAs, priority: str, due_at: str
    ) -> None:
        created = post_ticket(client, login_as(REQUESTER_USERNAME), priority=priority)
        assert (created.json()["priority"], created.json()["sla"]["due_at"]) == (
            priority,
            due_at,
        )

    def test_the_default_priority_uses_the_medium_deadline(
        self, created: Response
    ) -> None:
        assert created.json()["sla"]["due_at"] == "2026-10-22T13:05:00Z"

    def test_a_ticket_created_after_hours_starts_counting_on_the_next_workday(
        self, client: TestClient, login_as: LoginAs, clock: FakeClock
    ) -> None:
        clock.set(SANTIAGO_FRIDAY_EVENING)
        created = post_ticket(client, login_as(REQUESTER_USERNAME), priority="high")
        assert created.json()["sla"]["due_at"] == "2026-10-26T21:00:00Z"  # lunes 18:00

    def test_the_text_is_stored_without_surrounding_spaces(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        created = post_ticket(
            client,
            login_as(REQUESTER_USERNAME),
            title="  Teclado roto \n",
            description="\t Dos teclas no responden. ",
        )
        assert (created.json()["title"], created.json()["description"]) == (
            "Teclado roto",
            "Dos teclas no responden.",
        )

    def test_the_client_cannot_choose_who_owns_or_handles_the_ticket(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        created = post_ticket(
            client,
            login_as(REQUESTER_USERNAME),
            requester_id=OTHER_REQUESTER_ID,
            assignee_id=AGENT_ID,
            status="closed",
        )
        ticket = created.json()
        assert (ticket["requester"]["id"], ticket["assignee"], ticket["status"]) == (
            REQUESTER_ID,
            None,
            "open",
        )

    def test_an_agent_cannot_create_tickets(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = post_ticket(client, login_as(AGENT_USERNAME))
        assert (response.status_code, response.json()["code"]) == (403, "forbidden")

    def test_creation_requires_a_session(self, client: TestClient) -> None:
        response = client.post(TICKETS_URL, json=NEW_TICKET)
        assert (response.status_code, response.json()["code"]) == (
            401,
            "not_authenticated",
        )


@pytest.mark.usefixtures("demo_data")
class TestCreationValidation:
    @pytest.mark.parametrize("field", ["title", "description", "category_id"])
    def test_a_missing_field_is_reported(
        self, client: TestClient, login_as: LoginAs, field: str
    ) -> None:
        body = {key: value for key, value in NEW_TICKET.items() if key != field}
        response = client.post(
            TICKETS_URL, headers=login_as(REQUESTER_USERNAME), json=body
        )
        assert invalid_field(response) == ["body", field]

    @pytest.mark.parametrize("field", ["title", "description"])
    @pytest.mark.parametrize("empty", ["", "   ", "\t\n "])
    def test_empty_or_blank_text_is_rejected(
        self, client: TestClient, login_as: LoginAs, field: str, empty: str
    ) -> None:
        response = post_ticket(client, login_as(REQUESTER_USERNAME), **{field: empty})
        assert invalid_field(response) == ["body", field]

    @pytest.mark.parametrize(
        ("field", "limit"),
        [("title", TITLE_MAX_LENGTH), ("description", DESCRIPTION_MAX_LENGTH)],
    )
    def test_text_at_the_limit_is_accepted(
        self, client: TestClient, login_as: LoginAs, field: str, limit: int
    ) -> None:
        response = post_ticket(
            client, login_as(REQUESTER_USERNAME), **{field: "a" * limit}
        )
        assert response.status_code == 201

    @pytest.mark.parametrize(
        ("field", "limit"),
        [("title", TITLE_MAX_LENGTH), ("description", DESCRIPTION_MAX_LENGTH)],
    )
    def test_text_one_character_over_the_limit_is_rejected(
        self, client: TestClient, login_as: LoginAs, field: str, limit: int
    ) -> None:
        response = post_ticket(
            client, login_as(REQUESTER_USERNAME), **{field: "a" * (limit + 1)}
        )
        assert invalid_field(response) == ["body", field]

    @pytest.mark.parametrize(
        ("field", "limit"),
        [("title", TITLE_MAX_LENGTH), ("description", DESCRIPTION_MAX_LENGTH)],
    )
    def test_the_limit_counts_the_text_without_surrounding_spaces(
        self, client: TestClient, login_as: LoginAs, field: str, limit: int
    ) -> None:
        padded = f"  {'a' * limit}  "
        response = post_ticket(client, login_as(REQUESTER_USERNAME), **{field: padded})
        assert response.status_code == 201

    def test_an_unknown_category_is_rejected(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = post_ticket(client, login_as(REQUESTER_USERNAME), category_id=99)
        assert invalid_field(response) == ["body", "category_id"]

    def test_an_unknown_category_explains_itself_in_spanish(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = post_ticket(client, login_as(REQUESTER_USERNAME), category_id=99)
        assert response.json()["detail"] == [
            {
                "type": "value_error",
                "loc": ["body", "category_id"],
                "msg": "La categoría no existe.",
            }
        ]

    @pytest.mark.parametrize("priority", ["urgent", "", None])
    def test_an_unknown_priority_is_rejected(
        self, client: TestClient, login_as: LoginAs, priority: str | None
    ) -> None:
        response = post_ticket(client, login_as(REQUESTER_USERNAME), priority=priority)
        assert invalid_field(response) == ["body", "priority"]

    def test_a_rejected_ticket_is_not_created(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        post_ticket(client, headers, title="   ")
        post_ticket(client, headers, category_id=99)
        assert client.get(TICKETS_URL, headers=headers).json() == []


@pytest.mark.usefixtures("demo_data")
class TestMyTickets:
    def test_a_requester_without_tickets_gets_an_empty_list(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = client.get(TICKETS_URL, headers=login_as(REQUESTER_USERNAME))
        assert (response.status_code, response.json()) == (200, [])

    def test_lists_only_the_tickets_of_the_requester(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        add_ticket(session, title="Mío")
        add_ticket(session, title="De Bruno", requester_id=OTHER_REQUESTER_ID)
        titles = [
            ticket["title"]
            for ticket in client.get(
                TICKETS_URL, headers=login_as(REQUESTER_USERNAME)
            ).json()
        ]
        assert titles == ["Mío"]

    def test_lists_the_newest_first(
        self, client: TestClient, login_as: LoginAs, clock: FakeClock
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        for title in ("Primero", "Segundo", "Tercero"):
            post_ticket(client, headers, title=title)
            clock.advance(timedelta(hours=1))
        titles = [t["title"] for t in client.get(TICKETS_URL, headers=headers).json()]
        assert titles == ["Tercero", "Segundo", "Primero"]

    def test_tickets_created_at_the_same_instant_list_the_last_one_first(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        for title in ("Primero", "Segundo"):
            post_ticket(client, headers, title=title)
        titles = [t["title"] for t in client.get(TICKETS_URL, headers=headers).json()]
        assert titles == ["Segundo", "Primero"]

    def test_a_listed_ticket_has_the_summary_fields(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        post_ticket(client, headers)
        (ticket,) = client.get(TICKETS_URL, headers=headers).json()
        assert set(ticket) == {
            "id",
            "title",
            "status",
            "priority",
            "category",
            "requester",
            "assignee",
            "created_at",
            "sla",
        }

    def test_a_listed_ticket_without_agent_has_no_assignee(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        post_ticket(client, headers)
        (ticket,) = client.get(TICKETS_URL, headers=headers).json()
        assert ticket["assignee"] is None

    def test_a_listed_ticket_names_its_agent(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        add_ticket(session, status=TicketStatus.IN_PROGRESS, assignee_id=AGENT_ID)
        (ticket,) = client.get(TICKETS_URL, headers=login_as(REQUESTER_USERNAME)).json()
        assert ticket["assignee"] == {"id": AGENT_ID, "name": "Elena Vidal"}

    def test_every_status_is_listed(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        for status in TicketStatus:
            add_ticket(session, status=status, resolved_at=CREATED_AT)
        statuses = {
            ticket["status"]
            for ticket in client.get(
                TICKETS_URL, headers=login_as(REQUESTER_USERNAME)
            ).json()
        }
        assert statuses == {status.value for status in TicketStatus}

    def test_view_mine_is_the_default_view(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        add_ticket(session)
        headers = login_as(REQUESTER_USERNAME)
        assert (
            client.get(TICKETS_URL, params={"view": "mine"}, headers=headers).json()
            == client.get(TICKETS_URL, headers=headers).json()
        )

    @pytest.mark.parametrize("view", ["queue", "assigned"])
    def test_a_requester_cannot_ask_for_the_agent_views(
        self, client: TestClient, login_as: LoginAs, view: str
    ) -> None:
        response = client.get(
            TICKETS_URL, params={"view": view}, headers=login_as(REQUESTER_USERNAME)
        )
        assert (response.status_code, response.json()["code"]) == (403, "forbidden")

    @pytest.mark.parametrize("view", [None, "queue", "assigned", "mine"])
    def test_an_agent_has_no_list_available_yet(
        self, client: TestClient, login_as: LoginAs, view: str | None
    ) -> None:
        params = {} if view is None else {"view": view}
        response = client.get(
            TICKETS_URL, params=params, headers=login_as(AGENT_USERNAME)
        )
        assert (response.status_code, response.json()["code"]) == (403, "forbidden")

    def test_an_unknown_view_is_a_validation_error(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = client.get(
            TICKETS_URL,
            params={"view": "everything"},
            headers=login_as(REQUESTER_USERNAME),
        )
        assert invalid_field(response) == ["query", "view"]

    def test_the_list_requires_a_session(self, client: TestClient) -> None:
        assert client.get(TICKETS_URL).status_code == 401


@pytest.mark.usefixtures("demo_data")
class TestSlaOfListedTickets:
    """El estado del SLA se deriva al leer, con el reloj y el calendario inyectados."""

    @pytest.fixture
    def sla_of_only_ticket(
        self, client: TestClient, login_as: LoginAs
    ) -> Callable[[], dict[str, Any]]:
        def read() -> dict[str, Any]:
            (ticket,) = client.get(
                TICKETS_URL, headers=login_as(REQUESTER_USERNAME)
            ).json()
            sla: dict[str, Any] = ticket["sla"]
            return sla

        return read

    def test_a_ticket_past_its_deadline_is_breached(
        self, session: Session, sla_of_only_ticket: Callable[[], dict[str, Any]]
    ) -> None:
        add_ticket(session, sla_due_at=CREATED_AT - timedelta(hours=1))
        assert sla_of_only_ticket() == {
            "state": "breached",
            "due_at": "2026-10-19T12:05:00Z",
        }

    def test_a_ticket_close_to_its_deadline_is_at_risk(
        self, session: Session, sla_of_only_ticket: Callable[[], dict[str, Any]]
    ) -> None:
        add_ticket(session, sla_due_at=CREATED_AT + timedelta(minutes=30))
        assert sla_of_only_ticket()["state"] == "at_risk"

    def test_a_ticket_on_hold_is_paused_and_has_no_deadline(
        self, session: Session, sla_of_only_ticket: Callable[[], dict[str, Any]]
    ) -> None:
        add_ticket(
            session,
            status=TicketStatus.ON_HOLD,
            assignee_id=AGENT_ID,
            on_hold_since=CREATED_AT,
        )
        assert sla_of_only_ticket() == {"state": "paused", "due_at": None}

    def test_a_cancelled_ticket_has_no_sla(
        self, session: Session, sla_of_only_ticket: Callable[[], dict[str, Any]]
    ) -> None:
        add_ticket(session, status=TicketStatus.CANCELLED, cancelled_at=CREATED_AT)
        assert sla_of_only_ticket() == {"state": None, "due_at": None}

    def test_a_ticket_resolved_in_time_is_met(
        self, session: Session, sla_of_only_ticket: Callable[[], dict[str, Any]]
    ) -> None:
        add_ticket(session, status=TicketStatus.RESOLVED, resolved_at=CREATED_AT)
        assert sla_of_only_ticket()["state"] == "met"


@pytest.mark.usefixtures("demo_data")
class TestDetail:
    def test_the_owner_reads_the_detail(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        created = post_ticket(client, headers).json()
        response = client.get(f"{TICKETS_URL}/{created['id']}", headers=headers)
        assert (response.status_code, response.json()) == (200, created)

    def test_another_requesters_ticket_looks_nonexistent(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        foreign_id = add_ticket_id(session, requester_id=OTHER_REQUESTER_ID)
        response = client.get(
            f"{TICKETS_URL}/{foreign_id}", headers=login_as(REQUESTER_USERNAME)
        )
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    def test_a_nonexistent_ticket_answers_the_same_as_a_foreign_one(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = client.get(
            f"{TICKETS_URL}/999", headers=login_as(REQUESTER_USERNAME)
        )
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    def test_an_agent_reads_a_ticket_of_any_requester(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session, requester_id=OTHER_REQUESTER_ID)
        response = client.get(
            f"{TICKETS_URL}/{ticket_id}", headers=login_as(AGENT_USERNAME)
        )
        assert (response.status_code, response.json()["requester"]["id"]) == (
            200,
            OTHER_REQUESTER_ID,
        )

    def test_an_agent_is_offered_the_agent_actions(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        response = client.get(
            f"{TICKETS_URL}/{ticket_id}", headers=login_as(AGENT_USERNAME)
        )
        assert response.json()["allowed_actions"] == [
            "take",
            "comment",
            "change_priority",
        ]

    def test_a_non_numeric_id_is_a_validation_error(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        response = client.get(
            f"{TICKETS_URL}/abc", headers=login_as(REQUESTER_USERNAME)
        )
        assert invalid_field(response) == ["path", "ticket_id"]

    def test_the_detail_requires_a_session(self, client: TestClient) -> None:
        assert client.get(f"{TICKETS_URL}/1").status_code == 401


@pytest.mark.usefixtures("demo_data")
class TestCancellation:
    @pytest.fixture
    def headers(self, login_as: LoginAs) -> dict[str, str]:
        return login_as(REQUESTER_USERNAME)

    @pytest.fixture
    def open_ticket(self, client: TestClient, headers: dict[str, str]) -> int:
        ticket_id: int = post_ticket(client, headers).json()["id"]
        return ticket_id

    def cancel(
        self, client: TestClient, headers: dict[str, str], ticket_id: int
    ) -> Response:
        return client.post(
            transitions_url(ticket_id), headers=headers, json={"action": "cancel"}
        )

    def test_cancelling_an_open_ticket_leaves_it_cancelled(
        self, client: TestClient, headers: dict[str, str], open_ticket: int
    ) -> None:
        response = self.cancel(client, headers, open_ticket)
        assert (response.status_code, response.json()["status"]) == (200, "cancelled")

    def test_records_the_cancellation_instant(
        self,
        client: TestClient,
        headers: dict[str, str],
        open_ticket: int,
        clock: FakeClock,
    ) -> None:
        clock.advance(timedelta(minutes=10))
        response = self.cancel(client, headers, open_ticket)
        assert response.json()["cancelled_at"] == "2026-10-19T13:15:00Z"

    def test_a_cancelled_ticket_offers_no_actions(
        self, client: TestClient, headers: dict[str, str], open_ticket: int
    ) -> None:
        response = self.cancel(client, headers, open_ticket)
        assert response.json()["allowed_actions"] == []

    def test_a_cancelled_ticket_has_no_sla(
        self, client: TestClient, headers: dict[str, str], open_ticket: int
    ) -> None:
        response = self.cancel(client, headers, open_ticket)
        assert response.json()["sla"] == {"state": None, "due_at": None}

    def test_the_status_change_is_recorded_in_the_history(
        self,
        client: TestClient,
        headers: dict[str, str],
        open_ticket: int,
        session: Session,
    ) -> None:
        self.cancel(client, headers, open_ticket)
        created, changed = list_events(session, open_ticket)
        assert (
            created.kind,
            changed.kind,
            changed.actor_id,
            changed.from_value,
            changed.to_value,
        ) == (
            EventKind.CREATED,
            EventKind.STATUS_CHANGED,
            REQUESTER_ID,
            "open",
            "cancelled",
        )

    def test_the_cancellation_persists(
        self, client: TestClient, headers: dict[str, str], open_ticket: int
    ) -> None:
        self.cancel(client, headers, open_ticket)
        (listed,) = client.get(TICKETS_URL, headers=headers).json()
        assert listed["status"] == "cancelled"

    def test_cancelling_twice_is_rejected(
        self, client: TestClient, headers: dict[str, str], open_ticket: int
    ) -> None:
        self.cancel(client, headers, open_ticket)
        again = self.cancel(client, headers, open_ticket)
        assert (again.status_code, again.json()["code"]) == (409, "action_not_allowed")

    @pytest.mark.parametrize(
        "status",
        [
            TicketStatus.IN_PROGRESS,
            TicketStatus.ON_HOLD,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
        ],
    )
    def test_a_ticket_that_is_not_open_cannot_be_cancelled(
        self,
        client: TestClient,
        headers: dict[str, str],
        session: Session,
        status: TicketStatus,
    ) -> None:
        ticket_id = add_ticket_id(session, status=status, resolved_at=CREATED_AT)
        response = self.cancel(client, headers, ticket_id)
        assert (response.status_code, response.json()["code"]) == (
            409,
            "action_not_allowed",
        )

    def test_the_rejection_explains_the_current_status(
        self, client: TestClient, headers: dict[str, str], session: Session
    ) -> None:
        ticket_id = add_ticket_id(session, status=TicketStatus.IN_PROGRESS)
        response = self.cancel(client, headers, ticket_id)
        assert response.json()["message"] == (
            "La acción «Cancelar» no está disponible con el ticket en estado «En progreso»."
        )

    def test_a_rejected_cancellation_changes_nothing(
        self, client: TestClient, headers: dict[str, str], session: Session
    ) -> None:
        ticket_id = add_ticket_id(session, status=TicketStatus.IN_PROGRESS)
        self.cancel(client, headers, ticket_id)
        ticket = reload(session, ticket_id)
        assert (
            ticket.status,
            ticket.cancelled_at,
            list_events(session, ticket_id),
        ) == (
            TicketStatus.IN_PROGRESS,
            None,
            [],
        )

    def test_another_requester_cannot_cancel_the_ticket(
        self, client: TestClient, headers: dict[str, str], session: Session
    ) -> None:
        foreign_id = add_ticket_id(session, requester_id=OTHER_REQUESTER_ID)
        response = self.cancel(client, headers, foreign_id)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    def test_an_agent_cannot_cancel(
        self, client: TestClient, login_as: LoginAs, open_ticket: int
    ) -> None:
        response = self.cancel(client, login_as(AGENT_USERNAME), open_ticket)
        assert (response.status_code, response.json()["code"]) == (403, "forbidden")

    def test_cancelling_a_nonexistent_ticket_answers_404(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        response = self.cancel(client, headers, 999)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)


@pytest.mark.usefixtures("demo_data")
class TestTransitionRequests:
    @pytest.fixture
    def headers(self, login_as: LoginAs) -> dict[str, str]:
        return login_as(REQUESTER_USERNAME)

    def request(
        self, client: TestClient, headers: dict[str, str], ticket_id: int, action: str
    ) -> Response:
        return client.post(
            transitions_url(ticket_id), headers=headers, json={"action": action}
        )

    @pytest.mark.parametrize(
        "status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD]
    )
    def test_closing_a_ticket_that_is_not_resolved_is_rejected(
        self,
        client: TestClient,
        headers: dict[str, str],
        session: Session,
        status: TicketStatus,
    ) -> None:
        ticket_id = add_ticket_id(session, status=status)
        response = self.request(client, headers, ticket_id, "close")
        assert (response.status_code, response.json()["code"]) == (
            409,
            "action_not_allowed",
        )

    def test_an_agent_cannot_close_a_ticket(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session, status=TicketStatus.IN_PROGRESS)
        response = self.request(client, login_as(AGENT_USERNAME), ticket_id, "close")
        assert (response.status_code, response.json()["code"]) == (403, "forbidden")

    @pytest.mark.parametrize("action", ["comment", "change_priority", "archive", ""])
    def test_only_state_actions_are_accepted(
        self,
        client: TestClient,
        headers: dict[str, str],
        session: Session,
        action: str,
    ) -> None:
        ticket_id = add_ticket_id(session)
        response = self.request(client, headers, ticket_id, action)
        assert invalid_field(response) == ["body", "action"]

    def test_a_missing_action_is_rejected(
        self, client: TestClient, headers: dict[str, str], session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        response = client.post(transitions_url(ticket_id), headers=headers, json={})
        assert invalid_field(response) == ["body", "action"]

    def test_transitions_require_a_session(self, client: TestClient) -> None:
        response = client.post(transitions_url(1), json={"action": "cancel"})
        assert (response.status_code, response.json()["code"]) == (
            401,
            "not_authenticated",
        )

    @pytest.mark.parametrize(
        ("action", "username", "initial", "expected"),
        [
            ("hold", AGENT_USERNAME, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD),
            (
                "resolve",
                AGENT_USERNAME,
                TicketStatus.IN_PROGRESS,
                TicketStatus.RESOLVED,
            ),
            ("close", REQUESTER_USERNAME, TicketStatus.RESOLVED, TicketStatus.CLOSED),
            (
                "reopen",
                REQUESTER_USERNAME,
                TicketStatus.RESOLVED,
                TicketStatus.IN_PROGRESS,
            ),
        ],
    )
    def test_the_generic_mechanism_moves_the_other_state_actions(
        self,
        client: TestClient,
        login_as: LoginAs,
        session: Session,
        action: str,
        username: str,
        initial: TicketStatus,
        expected: TicketStatus,
    ) -> None:
        ticket_id = add_ticket_id(
            session,
            status=initial,
            assignee_id=AGENT_ID,
            resolved_at=CREATED_AT if initial == TicketStatus.RESOLVED else None,
        )
        response = self.request(client, login_as(username), ticket_id, action)
        assert (response.status_code, response.json()["status"]) == (200, expected)

    @pytest.mark.parametrize(
        ("action", "username", "initial", "field", "expected"),
        [
            ("hold", AGENT_USERNAME, TicketStatus.IN_PROGRESS, "on_hold_since", True),
            ("resolve", AGENT_USERNAME, TicketStatus.IN_PROGRESS, "resolved_at", True),
            ("close", REQUESTER_USERNAME, TicketStatus.RESOLVED, "closed_at", True),
            ("reopen", REQUESTER_USERNAME, TicketStatus.RESOLVED, "resolved_at", False),
        ],
    )
    def test_each_action_stamps_or_clears_its_date(
        self,
        client: TestClient,
        login_as: LoginAs,
        session: Session,
        clock: FakeClock,
        action: str,
        username: str,
        initial: TicketStatus,
        field: str,
        expected: bool,
    ) -> None:
        ticket_id = add_ticket_id(
            session,
            status=initial,
            assignee_id=AGENT_ID,
            resolved_at=CREATED_AT if initial == TicketStatus.RESOLVED else None,
        )
        clock.advance(timedelta(hours=2))
        self.request(client, login_as(username), ticket_id, action)
        stamped = getattr(reload(session, ticket_id), field)
        assert stamped == (clock.now() if expected else None)

    @pytest.mark.parametrize("action", ["take", "resume"])
    def test_actions_that_arrive_with_the_agent_queue_are_not_available_yet(
        self,
        client: TestClient,
        login_as: LoginAs,
        session: Session,
        action: str,
    ) -> None:
        ticket_id = add_ticket_id(
            session,
            status=TicketStatus.ON_HOLD if action == "resume" else TicketStatus.OPEN,
            assignee_id=AGENT_ID,
            on_hold_since=CREATED_AT,
        )
        response = self.request(client, login_as(AGENT_USERNAME), ticket_id, action)
        assert (response.status_code, response.json()["code"]) == (
            409,
            "action_not_allowed",
        )
