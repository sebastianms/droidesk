from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.factories import AGENT_USERNAME, REQUESTER_USERNAME

LoginAs = Callable[[str], dict[str, str]]
PROFILES = [REQUESTER_USERNAME, AGENT_USERNAME]
CATALOGS = ["/api/v1/categories", "/api/v1/sla-policies"]


@pytest.mark.usefixtures("demo_data")
@pytest.mark.parametrize("path", CATALOGS)
def test_catalogs_require_a_session(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert (response.status_code, response.json()["code"]) == (401, "not_authenticated")


@pytest.mark.parametrize("username", PROFILES)
def test_both_profiles_see_the_categories(
    client: TestClient, login_as: LoginAs, username: str
) -> None:
    names = [
        c["name"]
        for c in client.get("/api/v1/categories", headers=login_as(username)).json()
    ]
    assert names == [
        "Hardware",
        "Software",
        "Accesos y cuentas",
        "Red y conectividad",
        "Otro",
    ]


def test_categories_carry_id_and_name(client: TestClient, login_as: LoginAs) -> None:
    category = client.get(
        "/api/v1/categories", headers=login_as(REQUESTER_USERNAME)
    ).json()[0]
    assert category == {"id": 1, "name": "Hardware"}


@pytest.mark.parametrize("username", PROFILES)
def test_both_profiles_see_the_policies_by_rank(
    client: TestClient, login_as: LoginAs, username: str
) -> None:
    policies = client.get("/api/v1/sla-policies", headers=login_as(username)).json()
    assert [(p["rank"], p["priority"]) for p in policies] == [
        (1, "critical"),
        (2, "high"),
        (3, "medium"),
        (4, "low"),
    ]


@pytest.mark.parametrize(
    ("priority", "label", "amount", "unit"),
    [
        ("critical", "Crítica", 4, "hours"),
        ("high", "Alta", 1, "days"),
        ("medium", "Media", 3, "days"),
        ("low", "Baja", 5, "days"),
    ],
)
def test_each_policy_states_its_target(
    client: TestClient,
    login_as: LoginAs,
    priority: str,
    label: str,
    amount: int,
    unit: str,
) -> None:
    policies = client.get(
        "/api/v1/sla-policies", headers=login_as(REQUESTER_USERNAME)
    ).json()
    policy = next(p for p in policies if p["priority"] == priority)
    assert (policy["label"], policy["target_amount"], policy["target_unit"]) == (
        label,
        amount,
        unit,
    )


def test_each_policy_has_a_guiding_description(
    client: TestClient, login_as: LoginAs
) -> None:
    policies = client.get(
        "/api/v1/sla-policies", headers=login_as(REQUESTER_USERNAME)
    ).json()
    assert all(p["description"] for p in policies)
