from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine

from droidesk_api.core.config import Settings
from droidesk_api.core.errors import (
    ActionNotAllowedError,
    AlreadyTakenError,
    DomainError,
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
)
from droidesk_api.main import create_app

EXPECTED_OPERATION_IDS = {
    "read_health",
    "list_demo_users",
    "login",
    "read_me",
    "list_categories",
    "list_sla_policies",
    "create_ticket",
    "list_tickets",
    "read_ticket",
    "transition_ticket",
}
ERRORS: dict[str, Callable[[], DomainError]] = {
    "unauthenticated": NotAuthenticatedError,
    "forbidden": ForbiddenError,
    "not_found": NotFoundError,
    "taken": AlreadyTakenError,
    "not_allowed": ActionNotAllowedError,
    "custom": partial(ActionNotAllowedError, "El ticket ya está resuelto."),
}


@pytest.fixture
def pristine_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in ("DROIDESK_JWT_SECRET", "DROIDESK_BUSINESS_HOURS", "DROIDESK_TIMEZONE"):
        monkeypatch.delenv(name, raising=False)
    database = tmp_path / "never-created.db"
    monkeypatch.setenv("DROIDESK_DATABASE_URL", f"sqlite:///{database}")
    return database


def operations(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        operation for path in schema["paths"].values() for operation in path.values()
    ]


class TestCreation:
    def test_creating_the_app_needs_no_secret(self, pristine_environment: Path) -> None:
        assert create_app().openapi()["info"]["title"] == "DroiDesk API"

    def test_creating_the_app_does_not_touch_the_database(
        self, pristine_environment: Path
    ) -> None:
        create_app().openapi()
        assert not pristine_environment.exists()


class TestStartup:
    @pytest.fixture
    def environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
        settings: Settings,
        engine: Engine,
        demo_data: None,
    ) -> None:
        monkeypatch.setenv(
            "DROIDESK_JWT_SECRET", settings.jwt_secret.get_secret_value()
        )
        monkeypatch.setenv("DROIDESK_DATABASE_URL", settings.database_url)

    @pytest.mark.usefixtures("environment")
    def test_startup_builds_the_engine_and_shutdown_releases_it(self) -> None:
        app = create_app()
        with TestClient(app):
            engine = app.state.engine
            assert engine.pool.checkedout() == 0
        assert engine.pool.checkedout() == 0

    @pytest.mark.usefixtures("environment")
    def test_real_dependencies_log_a_user_in_end_to_end(self) -> None:
        with TestClient(create_app()) as client:
            credentials = {"username": "elena.vidal", "password": "cualquiera"}
            token = client.post("/api/v1/auth/login", json=credentials).json()[
                "access_token"
            ]
            me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["name"] == "Elena Vidal"

    @pytest.mark.usefixtures("environment")
    def test_startup_fails_with_an_inverted_workday(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DROIDESK_BUSINESS_HOURS", "18:00-09:00")
        with (
            pytest.raises(ValidationError, match="posterior a la apertura"),
            TestClient(create_app()),
        ):
            pass

    def test_startup_fails_without_the_secret(self, pristine_environment: Path) -> None:
        with (
            pytest.raises(ValidationError, match="jwt_secret"),
            TestClient(create_app()),
        ):
            pass


class TestOpenApi:
    @pytest.fixture
    def schema(self, app: FastAPI) -> dict[str, Any]:
        return app.openapi()

    def test_operation_ids_are_the_route_names(self, schema: dict[str, Any]) -> None:
        assert {
            operation["operationId"] for operation in operations(schema)
        } == EXPECTED_OPERATION_IDS

    def test_operation_ids_are_unique(self, schema: dict[str, Any]) -> None:
        ids = [operation["operationId"] for operation in operations(schema)]
        assert len(ids) == len(set(ids))

    def test_documentation_is_served_under_the_api_prefix(
        self, client: TestClient
    ) -> None:
        assert client.get("/api/docs").status_code == 200

    def test_schema_is_served_under_the_api_prefix(self, client: TestClient) -> None:
        assert client.get("/api/openapi.json").json()["info"]["title"] == "DroiDesk API"

    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/api/redoc", "/openapi.json"])
    def test_nothing_is_served_outside_the_api_prefix(
        self, client: TestClient, path: str
    ) -> None:
        assert client.get(path).status_code == 404

    def test_protected_routes_declare_the_bearer_scheme(
        self, schema: dict[str, Any]
    ) -> None:
        assert (
            schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
        )

    @pytest.mark.parametrize(
        ("path", "status"),
        [
            ("/api/v1/me", "401"),
            ("/api/v1/categories", "401"),
            ("/api/v1/sla-policies", "401"),
            ("/api/v1/auth/login", "401"),
        ],
    )
    def test_error_responses_are_typed_with_the_error_body(
        self, schema: dict[str, Any], path: str, status: str
    ) -> None:
        operation = next(iter(schema["paths"][path].values()))
        assert operation["responses"][status]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ErrorBody"}

    @pytest.mark.parametrize(
        ("path", "method", "statuses"),
        [
            ("/api/v1/tickets", "post", {"201", "401", "403", "422"}),
            ("/api/v1/tickets", "get", {"200", "401", "403", "422"}),
            ("/api/v1/tickets/{ticket_id}", "get", {"200", "401", "404", "422"}),
            (
                "/api/v1/tickets/{ticket_id}/transitions",
                "post",
                {"200", "401", "403", "404", "409", "422"},
            ),
        ],
    )
    def test_ticket_operations_document_the_responses_of_the_contract(
        self, schema: dict[str, Any], path: str, method: str, statuses: set[str]
    ) -> None:
        assert set(schema["paths"][path][method]["responses"]) == statuses

    def test_creating_a_ticket_answers_201_with_the_detail(
        self, schema: dict[str, Any]
    ) -> None:
        created = schema["paths"]["/api/v1/tickets"]["post"]["responses"]["201"]
        assert created["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/TicketDetail"
        }

    def test_ticket_schemas_use_the_names_of_the_contract(
        self, schema: dict[str, Any]
    ) -> None:
        names = set(schema["components"]["schemas"])
        assert {
            "TicketCreate",
            "TicketSummary",
            "TicketDetail",
            "TransitionRequest",
            "UserRef",
            "Sla",
            "TicketAction",
            "Event",
            "EventKind",
        } <= names

    def test_ticket_detail_extends_the_summary(self, schema: dict[str, Any]) -> None:
        summary = schema["components"]["schemas"]["TicketSummary"]["properties"]
        detail = schema["components"]["schemas"]["TicketDetail"]["properties"]
        assert set(detail) - set(summary) == {
            "description",
            "resolved_at",
            "closed_at",
            "cancelled_at",
            "allowed_actions",
            "history",
        }

    def test_new_tickets_declare_their_limits_and_default_priority(
        self, schema: dict[str, Any]
    ) -> None:
        properties = schema["components"]["schemas"]["TicketCreate"]["properties"]
        assert (
            (properties["title"]["minLength"], properties["title"]["maxLength"]),
            (
                properties["description"]["minLength"],
                properties["description"]["maxLength"],
            ),
            properties["priority"]["default"],
        ) == ((1, 120), (1, 5000), "medium")

    def test_transitions_accept_only_state_actions(
        self, schema: dict[str, Any]
    ) -> None:
        action = schema["components"]["schemas"]["TransitionRequest"]["properties"][
            "action"
        ]
        assert action["enum"] == [
            "take",
            "cancel",
            "hold",
            "resume",
            "resolve",
            "close",
            "reopen",
        ]

    def test_login_documents_the_unknown_user_and_the_validation_error(
        self, schema: dict[str, Any]
    ) -> None:
        login = schema["paths"]["/api/v1/auth/login"]["post"]
        assert set(login["responses"]) == {"200", "401", "422"}

    def test_login_no_longer_asks_for_a_role(self, schema: dict[str, Any]) -> None:
        request = schema["components"]["schemas"]["LoginRequest"]
        assert set(request["properties"]) == {"username", "password"}

    def test_demo_users_are_listed_without_authentication(
        self, schema: dict[str, Any]
    ) -> None:
        users = schema["paths"]["/api/v1/auth/users"]["get"]
        assert "security" not in users

    def test_login_password_is_a_write_only_secret(
        self, schema: dict[str, Any]
    ) -> None:
        password = schema["components"]["schemas"]["LoginRequest"]["properties"][
            "password"
        ]
        assert (password["format"], password["writeOnly"]) == ("password", True)

    def test_login_username_declares_its_pattern(self, schema: dict[str, Any]) -> None:
        username = schema["components"]["schemas"]["LoginRequest"]["properties"][
            "username"
        ]
        assert username["pattern"] == "^[a-z0-9._-]{1,50}$"

    def test_error_codes_are_an_enumeration(self, schema: dict[str, Any]) -> None:
        assert schema["components"]["schemas"]["ErrorCode"]["enum"] == [
            "not_authenticated",
            "forbidden",
            "not_found",
            "already_taken",
            "action_not_allowed",
        ]

    def test_schemas_use_the_names_of_the_contract(
        self, schema: dict[str, Any]
    ) -> None:
        names = set(schema["components"]["schemas"])
        assert {
            "User",
            "DemoUser",
            "LoginRequest",
            "LoginResponse",
            "Category",
            "SlaPolicy",
            "ErrorBody",
        } <= names


class TestValidationErrorHandler:
    def test_it_keeps_the_standard_422_shape_without_the_input(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/v1/auth/login", json={})
        assert (response.status_code, set(response.json()["detail"][0])) == (
            422,
            {"type", "loc", "msg"},
        )

    def test_it_keeps_the_context_of_the_error(self, client: TestClient) -> None:
        body = {"username": "ana.rojas", "password": ""}
        detail = client.post("/api/v1/auth/login", json=body).json()["detail"][0]
        assert (detail["loc"], detail["ctx"]["min_length"]) == (["body", "password"], 1)

    def test_it_reports_every_invalid_field(self, client: TestClient) -> None:
        body = {"username": "no válido", "password": ""}
        detail = client.post("/api/v1/auth/login", json=body).json()["detail"]
        assert [error["loc"][1] for error in detail] == ["username", "password"]


class TestErrorHandler:
    @pytest.fixture
    def failing_route(self, app: FastAPI) -> None:
        def fail(error: str) -> None:
            raise ERRORS[error]()

        app.add_api_route("/boom/{error}", fail)

    @pytest.mark.usefixtures("failing_route")
    @pytest.mark.parametrize(
        ("error", "status", "code"),
        [
            ("unauthenticated", 401, "not_authenticated"),
            ("forbidden", 403, "forbidden"),
            ("not_found", 404, "not_found"),
            ("taken", 409, "already_taken"),
            ("not_allowed", 409, "action_not_allowed"),
        ],
    )
    def test_domain_errors_become_code_and_message(
        self, client: TestClient, error: str, status: int, code: str
    ) -> None:
        response = client.get(f"/boom/{error}")
        assert (
            response.status_code,
            set(response.json()),
            response.json()["code"],
        ) == (status, {"code", "message"}, code)

    @pytest.mark.usefixtures("failing_route")
    def test_a_custom_message_replaces_the_default(self, client: TestClient) -> None:
        assert (
            client.get("/boom/custom").json()["message"]
            == "El ticket ya está resuelto."
        )

    @pytest.mark.usefixtures("failing_route")
    def test_default_messages_are_in_spanish(self, client: TestClient) -> None:
        assert (
            client.get("/boom/taken").json()["message"]
            == "Este ticket ya fue tomado por otro agente."
        )
