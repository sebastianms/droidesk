from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

from droidesk_api.tickets.enums import TicketStatus
from tests.api.helpers import (
    NOT_FOUND,
    TICKETS_URL,
    LoginAs,
    add_ticket_in_id,
    comments_url,
    post_ticket,
)
from tests.factories import AGENT_USERNAME, REQUESTER_USERNAME

# El mayor entero con signo de 64 bits: lo que el driver de SQLite acepta como INTEGER.
LARGEST_ID = 2**63 - 1
# Cada id fuera de rango con el error de validación que lo rechaza antes de la base.
OUT_OF_RANGE = [
    pytest.param(0, "greater_than_equal", id="zero"),
    pytest.param(-1, "greater_than_equal", id="negative"),
    pytest.param(LARGEST_ID + 1, "less_than_equal", id="one-past-the-largest"),
    pytest.param(10**30, "less_than_equal", id="huge"),
]
Route = tuple[str, str, dict[str, str] | None]
TICKET_ROUTES = [
    pytest.param(("get", "", None), id="detail"),
    pytest.param(("post", "/transitions", {"action": "take"}), id="transition"),
    pytest.param(("post", "/comments", {"body": "Hola"}), id="comment"),
]
CallRoute = Callable[[Route, int], Response]
# FastAPI declara minimum y maximum de los esquemas como float: el máximo sale como 2**63.
PATH_LIMITS = (1, LARGEST_ID)
BODY_LIMITS = (1, float(LARGEST_ID))


@pytest.fixture
def agent(login_as: LoginAs) -> dict[str, str]:
    return login_as(AGENT_USERNAME)


@pytest.fixture
def call_route(client: TestClient, agent: dict[str, str]) -> CallRoute:
    def send(route: Route, ticket_id: int) -> Response:
        method, suffix, body = route
        return client.request(
            method, f"{TICKETS_URL}/{ticket_id}{suffix}", headers=agent, json=body
        )

    return send


def rejection(response: Response) -> tuple[int, list[str | int], str]:
    error = response.json()["detail"][0]
    return response.status_code, error["loc"], error["type"]


class TestTicketIdInPath:
    @pytest.mark.parametrize(("ticket_id", "error_type"), OUT_OF_RANGE)
    @pytest.mark.parametrize("route", TICKET_ROUTES)
    def test_an_id_out_of_range_is_rejected_with_422(
        self, call_route: CallRoute, route: Route, ticket_id: int, error_type: str
    ) -> None:
        assert rejection(call_route(route, ticket_id)) == (
            422,
            ["path", "ticket_id"],
            error_type,
        )

    @pytest.mark.parametrize("route", TICKET_ROUTES)
    def test_the_rejection_does_not_echo_the_id(
        self, call_route: CallRoute, route: Route
    ) -> None:
        detail = call_route(route, LARGEST_ID + 1).json()["detail"]
        assert all("input" not in error for error in detail)

    @pytest.mark.parametrize("route", TICKET_ROUTES)
    def test_the_largest_id_that_fits_is_a_ticket_that_does_not_exist(
        self, call_route: CallRoute, route: Route
    ) -> None:
        response = call_route(route, LARGEST_ID)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)


class TestCategoryId:
    @pytest.fixture
    def create(
        self, client: TestClient, login_as: LoginAs
    ) -> Callable[[int], Response]:
        headers = login_as(REQUESTER_USERNAME)
        return lambda category_id: post_ticket(client, headers, category_id=category_id)

    @pytest.mark.parametrize(("category_id", "error_type"), OUT_OF_RANGE)
    def test_an_id_out_of_range_is_rejected_with_422(
        self, create: Callable[[int], Response], category_id: int, error_type: str
    ) -> None:
        assert rejection(create(category_id)) == (
            422,
            ["body", "category_id"],
            error_type,
        )

    def test_the_rejection_does_not_echo_the_id(
        self, create: Callable[[int], Response]
    ) -> None:
        detail = create(LARGEST_ID + 1).json()["detail"]
        assert all("input" not in error for error in detail)

    def test_the_largest_id_that_fits_is_a_category_that_does_not_exist(
        self, create: Callable[[int], Response]
    ) -> None:
        response = create(LARGEST_ID)
        assert (response.status_code, response.json()["detail"][0]["msg"]) == (
            422,
            "La categoría no existe.",
        )


class TestReplyToId:
    @pytest.fixture
    def reply(
        self, client: TestClient, agent: dict[str, str], session: Session
    ) -> Callable[[int], Response]:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        return lambda reply_to_id: client.post(
            comments_url(ticket_id),
            headers=agent,
            json={"body": "Hola", "reply_to_id": reply_to_id},
        )

    @pytest.mark.parametrize(("reply_to_id", "error_type"), OUT_OF_RANGE)
    def test_an_id_out_of_range_is_rejected_with_422(
        self, reply: Callable[[int], Response], reply_to_id: int, error_type: str
    ) -> None:
        assert rejection(reply(reply_to_id)) == (
            422,
            ["body", "reply_to_id"],
            error_type,
        )

    def test_the_rejection_does_not_echo_the_id(
        self, reply: Callable[[int], Response]
    ) -> None:
        detail = reply(LARGEST_ID + 1).json()["detail"]
        assert all("input" not in error for error in detail)

    def test_the_largest_id_that_fits_is_a_comment_that_does_not_exist(
        self, reply: Callable[[int], Response]
    ) -> None:
        response = reply(LARGEST_ID)
        assert (response.status_code, response.json()["detail"][0]["msg"]) == (
            422,
            "El comentario al que respondes no existe en este ticket.",
        )


class TestContract:
    @pytest.fixture
    def schema(self, app: FastAPI) -> dict[str, Any]:
        return app.openapi()

    @pytest.mark.parametrize("route", TICKET_ROUTES)
    def test_every_ticket_route_publishes_the_limits_of_its_id(
        self, schema: dict[str, Any], route: Route
    ) -> None:
        method, suffix, _body = route
        operation = schema["paths"][f"/api/v1/tickets/{{ticket_id}}{suffix}"][method]
        ticket_id = next(p for p in operation["parameters"] if p["name"] == "ticket_id")
        assert (
            ticket_id["schema"]["minimum"],
            ticket_id["schema"]["maximum"],
        ) == PATH_LIMITS

    def test_the_category_publishes_the_limits_of_its_id(
        self, schema: dict[str, Any]
    ) -> None:
        category = schema["components"]["schemas"]["TicketCreate"]["properties"][
            "category_id"
        ]
        assert (category["minimum"], category["maximum"]) == BODY_LIMITS

    def test_the_reply_publishes_the_limits_of_its_id(
        self, schema: dict[str, Any]
    ) -> None:
        reply = schema["components"]["schemas"]["CommentCreate"]["properties"][
            "reply_to_id"
        ]["anyOf"][0]
        assert (reply["minimum"], reply["maximum"]) == BODY_LIMITS
