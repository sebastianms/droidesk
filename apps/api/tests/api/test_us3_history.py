import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine, event
from sqlmodel import Session

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import NewEvent, record_event
from droidesk_api.core.db import persisted_id
from droidesk_api.tickets.enums import TicketStatus
from tests.api.helpers import (
    NOT_FOUND,
    Act,
    LoginAs,
    Read,
    add_ticket_id,
    add_ticket_in_id,
    post_ticket,
)
from tests.factories import (
    AGENT_ID,
    AGENT_USERNAME,
    CREATED_AT,
    OTHER_REQUESTER_USERNAME,
    REQUESTER_ID,
    REQUESTER_USERNAME,
    add_ticket,
)
from tests.fakes import FakeClock

HOUR = timedelta(hours=1)
Entry = tuple[str, str, str | None, str | None]
# Cada paso ocurre una hora después del anterior, desde la creación.
JOURNEY = [
    (AGENT_USERNAME, "take"),
    (AGENT_USERNAME, "hold"),
    (AGENT_USERNAME, "resume"),
    (AGENT_USERNAME, "resolve"),
    (REQUESTER_USERNAME, "close"),
]
JOURNEY_TRAIL: list[Entry] = [
    ("created", "Ana Rojas", None, "open"),
    ("assigned", "Elena Vidal", None, "Elena Vidal"),
    ("status_changed", "Elena Vidal", "open", "in_progress"),
    ("status_changed", "Elena Vidal", "in_progress", "on_hold"),
    ("status_changed", "Elena Vidal", "on_hold", "in_progress"),
    ("status_changed", "Elena Vidal", "in_progress", "resolved"),
    ("status_changed", "Ana Rojas", "resolved", "closed"),
]
JOURNEY_INSTANTS = [
    "2026-10-19T13:05:00Z",
    "2026-10-19T14:05:00Z",
    "2026-10-19T14:05:00Z",
    "2026-10-19T15:05:00Z",
    "2026-10-19T16:05:00Z",
    "2026-10-19T17:05:00Z",
    "2026-10-19T18:05:00Z",
]


def history(response: Response) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = response.json()["history"]
    return events


def trail(response: Response) -> list[Entry]:
    return [
        (entry["kind"], entry["actor"]["name"], entry["from_value"], entry["to_value"])
        for entry in history(response)
    ]


@pytest.fixture
def journey(client: TestClient, login_as: LoginAs, act: Act, clock: FakeClock) -> int:
    """Un ticket creado, tomado, puesto en espera, retomado, resuelto y cerrado."""
    ticket_id: int = post_ticket(client, login_as(REQUESTER_USERNAME)).json()["id"]
    for username, action in JOURNEY:
        clock.advance(HOUR)
        act(username, ticket_id, action)
    return ticket_id


@pytest.mark.usefixtures("demo_data")
class TestRecording:
    def test_a_new_ticket_starts_with_its_creation(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        created = post_ticket(client, login_as(REQUESTER_USERNAME))
        assert history(created) == [
            {
                "id": 1,
                "kind": "created",
                "actor": {"id": REQUESTER_ID, "name": "Ana Rojas"},
                "from_value": None,
                "to_value": "open",
                "created_at": "2026-10-19T13:05:00Z",
            }
        ]

    def test_keeps_every_change_with_its_previous_and_new_value(
        self, read: Read, journey: int
    ) -> None:
        assert trail(read(REQUESTER_USERNAME, journey)) == JOURNEY_TRAIL

    def test_each_change_carries_the_instant_it_happened(
        self, read: Read, journey: int
    ) -> None:
        instants = [e["created_at"] for e in history(read(AGENT_USERNAME, journey))]
        assert instants == JOURNEY_INSTANTS

    def test_the_actor_is_identified_by_id_and_name(
        self, read: Read, journey: int
    ) -> None:
        taking = history(read(AGENT_USERNAME, journey))[1]
        assert taking["actor"] == {"id": AGENT_ID, "name": "Elena Vidal"}

    @pytest.mark.parametrize(
        ("status", "username", "action", "entry"),
        [
            (
                TicketStatus.OPEN,
                REQUESTER_USERNAME,
                "cancel",
                ("status_changed", "Ana Rojas", "open", "cancelled"),
            ),
            (
                TicketStatus.RESOLVED,
                REQUESTER_USERNAME,
                "close",
                ("status_changed", "Ana Rojas", "resolved", "closed"),
            ),
            (
                TicketStatus.RESOLVED,
                REQUESTER_USERNAME,
                "reopen",
                ("status_changed", "Ana Rojas", "resolved", "in_progress"),
            ),
        ],
    )
    def test_names_the_requester_when_the_requester_changes_the_status(
        self,
        act: Act,
        session: Session,
        status: TicketStatus,
        username: str,
        action: str,
        entry: Entry,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert trail(act(username, ticket_id, action)) == [entry]

    def test_a_transition_answers_with_the_history_including_the_new_events(
        self, act: Act, read: Read, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        answered = act(AGENT_USERNAME, ticket_id, "take")
        assert history(answered) == history(read(AGENT_USERNAME, ticket_id))

    def test_a_transition_appends_to_the_history(
        self, act: Act, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        assert [e[0] for e in trail(act(AGENT_USERNAME, ticket_id, "take"))] == [
            "assigned",
            "status_changed",
        ]

    def test_a_failed_transition_adds_nothing(
        self, act: Act, read: Read, journey: int
    ) -> None:
        act(AGENT_USERNAME, journey, "take")
        assert trail(read(AGENT_USERNAME, journey)) == JOURNEY_TRAIL


@pytest.mark.usefixtures("demo_data")
class TestOrder:
    def test_orders_by_instant_even_if_recorded_out_of_order(
        self, read: Read, session: Session
    ) -> None:
        ticket_id = persisted_id(add_ticket(session))
        for kind, delay in ((EventKind.ASSIGNED, 2 * HOUR), (EventKind.CREATED, HOUR)):
            new_event = NewEvent(
                ticket_id, REQUESTER_ID, kind, CREATED_AT + delay, to_value="x"
            )
            record_event(session, new_event)
        session.commit()
        kinds = [entry["kind"] for entry in history(read(AGENT_USERNAME, ticket_id))]
        assert kinds == ["created", "assigned"]

    def test_orders_by_recording_when_the_instant_is_the_same(
        self, read: Read, journey: int
    ) -> None:
        kinds = [entry[0] for entry in trail(read(AGENT_USERNAME, journey))[1:3]]
        assert kinds == ["assigned", "status_changed"]


@pytest.mark.usefixtures("demo_data")
class TestVisibility:
    def test_the_requester_sees_the_history_of_their_ticket(
        self, read: Read, journey: int
    ) -> None:
        assert len(history(read(REQUESTER_USERNAME, journey))) == len(JOURNEY_TRAIL)

    def test_an_agent_sees_the_same_history_as_the_requester(
        self, read: Read, journey: int
    ) -> None:
        assert history(read(AGENT_USERNAME, journey)) == history(
            read(REQUESTER_USERNAME, journey)
        )

    def test_another_requester_gets_not_found(self, read: Read, journey: int) -> None:
        response = read(OTHER_REQUESTER_USERNAME, journey)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    def test_a_ticket_without_events_has_an_empty_history(
        self, read: Read, session: Session
    ) -> None:
        assert history(read(AGENT_USERNAME, add_ticket_id(session))) == []


@pytest.mark.usefixtures("demo_data")
class TestCost:
    def queries_while(self, engine: Engine, call: Callable[[], Response]) -> int:
        count = 0

        def on_query(*_args: Any) -> None:
            nonlocal count
            count += 1

        event.listen(engine, "before_cursor_execute", on_query)
        try:
            call()
        finally:
            event.remove(engine, "before_cursor_execute", on_query)
        return count

    def test_reading_does_not_query_once_per_event(
        self,
        engine: Engine,
        read: Read,
        client: TestClient,
        login_as: LoginAs,
        journey: int,
    ) -> None:
        single_id = post_ticket(client, login_as(REQUESTER_USERNAME)).json()["id"]
        single = self.queries_while(engine, lambda: read(AGENT_USERNAME, single_id))
        full = self.queries_while(engine, lambda: read(AGENT_USERNAME, journey))
        assert full == single


class TestImmutability:
    def test_no_route_is_about_events_or_the_history(self, app: FastAPI) -> None:
        paths = [route.path for route in app.routes if isinstance(route, APIRoute)]
        assert [p for p in paths if "event" in p or "history" in p] == []

    def test_nothing_can_be_replaced_or_deleted(self, app: FastAPI) -> None:
        methods = {
            method
            for route in app.routes
            if isinstance(route, APIRoute)
            for method in route.methods or ()
        }
        assert methods & {"PUT", "DELETE"} == set()

    def test_no_request_body_takes_an_event(self, app: FastAPI) -> None:
        operations = [
            operation
            for path_item in app.openapi()["paths"].values()
            for operation in path_item.values()
        ]
        bodies = [json.dumps(operation.get("requestBody")) for operation in operations]
        assert [body for body in bodies if "schemas/Event" in body] == []
