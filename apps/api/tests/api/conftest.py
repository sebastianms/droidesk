from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tests.api.helpers import (
    TICKETS_URL,
    Act,
    LoginAs,
    PatchTicket,
    PostComment,
    PostReply,
    Read,
    comments_url,
    transitions_url,
)


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
def comment(client: TestClient, login_as: LoginAs) -> PostComment:
    def post(username: str, ticket_id: int, body: str) -> Response:
        return client.post(
            comments_url(ticket_id), headers=login_as(username), json={"body": body}
        )

    return post


@pytest.fixture
def reply(client: TestClient, login_as: LoginAs) -> PostReply:
    def post(
        username: str, ticket_id: int, body: str, reply_to_id: int | None
    ) -> Response:
        return client.post(
            comments_url(ticket_id),
            headers=login_as(username),
            json={"body": body, "reply_to_id": reply_to_id},
        )

    return post


@pytest.fixture
def patch_ticket(client: TestClient, login_as: LoginAs) -> PatchTicket:
    def patch(username: str, ticket_id: int, body: dict[str, Any]) -> Response:
        return client.patch(
            f"{TICKETS_URL}/{ticket_id}", headers=login_as(username), json=body
        )

    return patch
