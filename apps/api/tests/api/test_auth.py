import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session, select

from droidesk_api.core.config import Settings
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.identity.schemas import PASSWORD_MAX_LENGTH
from tests.factories import (
    AGENT_ID,
    AGENT_USERNAME,
    ANY_PASSWORD,
    REQUESTER_ID,
    REQUESTER_USERNAME,
)
from tests.fakes import FakeClock

LoginAs = Callable[[str], dict[str, str]]
LOGIN_URL = "/api/v1/auth/login"
USERS_URL = "/api/v1/auth/users"
CREDENTIALS = {"username": REQUESTER_USERNAME, "password": ANY_PASSWORD}
SECRET = "clave-que-nunca-debe-aparecer"
UNAUTHENTICATED = {
    "code": "not_authenticated",
    "message": "Tu sesión no es válida o expiró. Ingresa de nuevo.",
}


def log_in(client: TestClient, **overrides: Any) -> Response:
    return client.post(LOGIN_URL, json=CREDENTIALS | overrides)


def invalid_field(response: Response) -> list[str | int]:
    assert response.status_code == 422
    location: list[str | int] = response.json()["detail"][0]["loc"]
    return location


@pytest.mark.usefixtures("demo_data")
class TestDemoUsers:
    def test_the_list_is_public(self, client: TestClient) -> None:
        assert client.get(USERS_URL).status_code == 200

    def test_lists_four_requesters_before_three_agents(
        self, client: TestClient
    ) -> None:
        roles = [user["role"] for user in client.get(USERS_URL).json()]
        assert roles == ["requester"] * 4 + ["agent"] * 3

    def test_orders_each_profile_by_name(self, client: TestClient) -> None:
        names = [user["name"] for user in client.get(USERS_URL).json()]
        assert names == [
            "Ana Rojas",
            "Bruno Castillo",
            "Carla Mena",
            "Diego Fuentes",
            "Elena Vidal",
            "Felipe Araya",
            "Gabriela Soto",
        ]

    def test_exposes_only_username_name_and_role(self, client: TestClient) -> None:
        user = client.get(USERS_URL).json()[0]
        assert user == {
            "username": "ana.rojas",
            "name": "Ana Rojas",
            "role": "requester",
        }


@pytest.mark.usefixtures("demo_data")
class TestLogin:
    def test_returns_a_bearer_token(self, client: TestClient) -> None:
        assert log_in(client).json()["token_type"] == "bearer"

    @pytest.mark.parametrize(
        ("username", "user_id", "role"),
        [
            (REQUESTER_USERNAME, REQUESTER_ID, "requester"),
            (AGENT_USERNAME, AGENT_ID, "agent"),
        ],
    )
    def test_returns_the_stored_user(
        self, client: TestClient, username: str, user_id: int, role: str
    ) -> None:
        user = log_in(client, username=username).json()["user"]
        assert (user["id"], user["username"], user["role"]) == (user_id, username, role)

    def test_exposes_only_the_public_fields(self, client: TestClient) -> None:
        user = log_in(client).json()["user"]
        assert set(user) == {"id", "username", "name", "email", "role"}

    def test_expiry_is_eight_hours_ahead(
        self, client: TestClient, clock: FakeClock
    ) -> None:
        assert log_in(client).json()["expires_at"] == (
            clock.now() + timedelta(hours=8)
        ).isoformat().replace("+00:00", "Z")

    def test_token_carries_no_role(
        self, client: TestClient, settings: Settings
    ) -> None:
        token = log_in(client).json()["access_token"]
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"verify_exp": False, "verify_iat": False},
        )
        assert set(claims) == {"sub", "iat", "exp"}

    def test_the_token_opens_the_session_of_the_user(self, client: TestClient) -> None:
        token = log_in(client, username=AGENT_USERNAME).json()["access_token"]
        me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert (me.json()["username"], me.json()["role"]) == (AGENT_USERNAME, "agent")

    @pytest.mark.parametrize("username", ["ANA.ROJAS", "  ana.rojas  ", " Ana.Rojas\t"])
    def test_spaces_and_uppercase_do_not_make_another_user(
        self, client: TestClient, username: str
    ) -> None:
        assert log_in(client, username=username).json()["user"]["id"] == REQUESTER_ID

    def test_a_requested_role_is_ignored(self, client: TestClient) -> None:
        user = log_in(client, role="agent").json()["user"]
        assert user["role"] == "requester"


@pytest.mark.usefixtures("demo_data")
class TestLoginOfAnUnknownUser:
    def test_is_not_authenticated(self, client: TestClient) -> None:
        response = log_in(client, username="desconocido")
        assert (response.status_code, response.json()) == (
            401,
            {
                "code": "not_authenticated",
                "message": "El usuario no existe. Revisa los usuarios de demo en el ícono ?.",
            },
        )

    def test_asks_for_a_bearer_token(self, client: TestClient) -> None:
        response = log_in(client, username="desconocido")
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_creates_nobody(self, client: TestClient, session: Session) -> None:
        log_in(client, username="desconocido")
        assert len(session.exec(select(User)).all()) == 7

    def test_a_valid_but_unregistered_username_is_not_a_validation_error(
        self, client: TestClient
    ) -> None:
        assert log_in(client, username="x" * 50).status_code == 401


@pytest.mark.usefixtures("demo_data")
class TestLoginAcceptsAnyPassword:
    @pytest.mark.parametrize(
        "password",
        [
            "a",
            "x" * PASSWORD_MAX_LENGTH,
            "con espacios y ñandú",
            "' OR '1'='1",
            "  ",
            "<script>alert(1)</script>",
        ],
    )
    def test_any_password_is_accepted(self, client: TestClient, password: str) -> None:
        assert log_in(client, password=password).status_code == 200

    def test_two_passwords_enter_as_the_same_user(self, client: TestClient) -> None:
        first = log_in(client, password="una").json()["user"]["id"]
        assert log_in(client, password="otra").json()["user"]["id"] == first


class TestLoginValidation:
    @pytest.mark.parametrize(
        "username",
        ["", "   ", "ana rojas", "ñandú", "ana/rojas", "ana@droidesk.local", "x" * 51],
    )
    def test_an_invalid_username_is_rejected(
        self, client: TestClient, username: str
    ) -> None:
        assert invalid_field(log_in(client, username=username)) == ["body", "username"]

    @pytest.mark.parametrize("password", ["", "x" * (PASSWORD_MAX_LENGTH + 1)])
    def test_a_password_out_of_range_is_rejected(
        self, client: TestClient, password: str
    ) -> None:
        assert invalid_field(log_in(client, password=password)) == ["body", "password"]

    @pytest.mark.parametrize("field", ["username", "password"])
    def test_a_missing_field_is_rejected(self, client: TestClient, field: str) -> None:
        body = {key: value for key, value in CREDENTIALS.items() if key != field}
        assert invalid_field(client.post(LOGIN_URL, json=body)) == ["body", field]

    @pytest.mark.parametrize("field", ["username", "password"])
    def test_a_value_that_is_not_text_is_rejected(
        self, client: TestClient, field: str
    ) -> None:
        assert invalid_field(log_in(client, **{field: 12345})) == ["body", field]

    def test_the_old_login_by_id_is_gone(self, client: TestClient) -> None:
        assert client.post(LOGIN_URL, json={"user_id": 1}).status_code == 422


@pytest.mark.usefixtures("demo_data")
class TestPasswordIsNeverExposed:
    def test_not_in_a_successful_response(self, client: TestClient) -> None:
        assert SECRET not in log_in(client, password=SECRET).text

    def test_not_in_the_response_of_an_unknown_user(self, client: TestClient) -> None:
        response = log_in(client, username="desconocido", password=SECRET)
        assert (response.status_code, SECRET in response.text) == (401, False)

    @pytest.mark.parametrize(
        "overrides",
        [{"password": SECRET * 6}, {"username": "con espacios"}],
        ids=["password too long", "invalid username"],
    )
    def test_not_in_a_validation_error(
        self, client: TestClient, overrides: dict[str, str]
    ) -> None:
        response = log_in(client, **({"password": SECRET} | overrides))
        assert (response.status_code, SECRET in response.text) == (422, False)

    def test_not_in_a_validation_error_for_a_missing_field(
        self, client: TestClient
    ) -> None:
        response = client.post(LOGIN_URL, json={"password": SECRET})
        assert (response.status_code, SECRET in response.text) == (422, False)

    def test_not_in_the_database(self, client: TestClient, session: Session) -> None:
        log_in(client, password=SECRET)
        rows = session.exec(select(User)).all()
        assert SECRET not in repr([row.model_dump() for row in rows])

    def test_not_in_the_logs(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            log_in(client, password=SECRET)
        assert SECRET not in caplog.text


@pytest.mark.usefixtures("demo_data")
class TestMe:
    def test_returns_the_user_of_the_token(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        user = client.get("/api/v1/me", headers=login_as(AGENT_USERNAME)).json()
        assert (user["id"], user["username"], user["name"], user["role"]) == (
            AGENT_ID,
            "elena.vidal",
            "Elena Vidal",
            "agent",
        )

    def test_requires_a_token(self, client: TestClient) -> None:
        response = client.get("/api/v1/me")
        assert (response.status_code, response.json()) == (401, UNAUTHENTICATED)

    def test_asks_for_a_bearer_token(self, client: TestClient) -> None:
        assert client.get("/api/v1/me").headers["WWW-Authenticate"] == "Bearer"

    def test_rejects_another_authorization_scheme(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/me", headers={"Authorization": "Basic YW5hOnNlY3JldA=="}
        )
        assert response.status_code == 401

    def test_rejects_a_garbage_token(self, client: TestClient) -> None:
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"})
        assert (response.status_code, response.json()) == (401, UNAUTHENTICATED)

    def test_rejects_an_expired_token(
        self, client: TestClient, login_as: LoginAs, clock: FakeClock
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        clock.advance(timedelta(hours=8))
        assert client.get("/api/v1/me", headers=headers).status_code == 401

    def test_accepts_a_token_until_it_expires(
        self, client: TestClient, login_as: LoginAs, clock: FakeClock
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        clock.advance(timedelta(hours=7, minutes=59))
        assert client.get("/api/v1/me", headers=headers).status_code == 200

    def test_rejects_a_token_of_a_user_that_no_longer_exists(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        session.delete(session.get_one(User, REQUESTER_ID))
        session.commit()
        assert client.get("/api/v1/me", headers=headers).status_code == 401

    def test_takes_the_role_from_the_database_not_from_the_token(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        headers = login_as(REQUESTER_USERNAME)
        session.get_one(User, REQUESTER_ID).role = Role.AGENT
        session.commit()
        assert client.get("/api/v1/me", headers=headers).json()["role"] == "agent"
