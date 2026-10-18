import os
import subprocess
import sys

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, func, select

from droidesk_api.core.config import Settings
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.seed import main, seed_demo_data
from droidesk_api.sla.enums import TargetUnit
from droidesk_api.sla.models import SlaPolicy
from droidesk_api.tickets.enums import Priority
from droidesk_api.tickets.models import Category


def count(session: Session, model: type[User | Category | SlaPolicy]) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def test_seeds_four_requesters_and_three_agents(session: Session) -> None:
    seed_demo_data(session)
    users = session.exec(select(User).order_by(col(User.id))).all()
    assert [u.role for u in users] == [Role.REQUESTER] * 4 + [Role.AGENT] * 3


def test_seeded_users_have_droidesk_local_emails(session: Session) -> None:
    seed_demo_data(session)
    assert all(u.email.endswith("@droidesk.local") for u in session.exec(select(User)))


def test_seeded_usernames_are_the_first_name_dot_surname(session: Session) -> None:
    seed_demo_data(session)
    users = session.exec(select(User).order_by(col(User.id)))
    assert [u.username for u in users] == [
        "ana.rojas",
        "bruno.castillo",
        "carla.mena",
        "diego.fuentes",
        "elena.vidal",
        "felipe.araya",
        "gabriela.soto",
    ]


def test_seeded_username_is_the_local_part_of_the_email(session: Session) -> None:
    seed_demo_data(session)
    users = session.exec(select(User))
    assert all(u.email == f"{u.username}@droidesk.local" for u in users)


def test_seeds_the_five_categories(session: Session) -> None:
    seed_demo_data(session)
    names = [c.name for c in session.exec(select(Category).order_by(col(Category.id)))]
    assert names == [
        "Hardware",
        "Software",
        "Accesos y cuentas",
        "Red y conectividad",
        "Otro",
    ]


@pytest.mark.parametrize(
    ("priority", "rank", "amount", "unit"),
    [
        (Priority.CRITICAL, 1, 4, TargetUnit.HOURS),
        (Priority.HIGH, 2, 1, TargetUnit.DAYS),
        (Priority.MEDIUM, 3, 3, TargetUnit.DAYS),
        (Priority.LOW, 4, 5, TargetUnit.DAYS),
    ],
)
def test_seeds_each_sla_policy(
    session: Session, priority: Priority, rank: int, amount: int, unit: TargetUnit
) -> None:
    seed_demo_data(session)
    policy = session.get_one(SlaPolicy, priority)
    assert (policy.rank, policy.target_amount, policy.target_unit) == (
        rank,
        amount,
        unit,
    )


def test_seed_reports_that_it_loaded(session: Session) -> None:
    assert seed_demo_data(session) is True


def test_seeding_twice_does_not_duplicate_anything(session: Session) -> None:
    seed_demo_data(session)
    assert seed_demo_data(session) is False
    assert (
        count(session, User),
        count(session, Category),
        count(session, SlaPolicy),
    ) == (7, 5, 4)


@pytest.mark.parametrize(
    "existing",
    [
        User(username="x", name="X", email="x@y.z", role=Role.AGENT),
        Category(name="Propia"),
    ],
)
def test_seed_leaves_a_database_with_data_alone(
    session: Session, existing: User | Category
) -> None:
    session.add(existing)
    session.commit()
    assert seed_demo_data(session) is False
    assert count(session, SlaPolicy) == 0


class TestMain:
    @pytest.fixture
    def environment(
        self, settings: Settings, engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "DROIDESK_JWT_SECRET", settings.jwt_secret.get_secret_value()
        )
        monkeypatch.setenv("DROIDESK_DATABASE_URL", settings.database_url)

    @pytest.mark.usefixtures("environment")
    def test_loads_the_demo_data_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_SEED_DEMO_DATA", "true")
        main()
        assert count(session, User) == 7

    @pytest.mark.usefixtures("environment")
    def test_loads_nothing_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_SEED_DEMO_DATA", "false")
        main()
        assert count(session, User) == 0

    @pytest.mark.usefixtures("environment")
    def test_running_twice_keeps_the_data_once(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_SEED_DEMO_DATA", "true")
        main()
        main()
        assert count(session, User) == 7

    @pytest.mark.usefixtures("environment")
    def test_reports_what_it_did(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("DROIDESK_SEED_DEMO_DATA", "true")
        with caplog.at_level("INFO"):
            main()
            main()
        assert [r.message for r in caplog.records] == [
            "Datos de demo cargados.",
            "Seed omitido: la base ya tiene datos.",
        ]


def test_runs_as_a_module_like_the_container_entrypoint(
    settings: Settings, engine: Engine, session: Session
) -> None:
    environment = {
        **os.environ,
        "DROIDESK_JWT_SECRET": settings.jwt_secret.get_secret_value(),
        "DROIDESK_DATABASE_URL": settings.database_url,
        "DROIDESK_SEED_DEMO_DATA": "true",
    }
    subprocess.run(
        [sys.executable, "-m", "droidesk_api.seed"], env=environment, check=True
    )
    assert count(session, User) == 7
