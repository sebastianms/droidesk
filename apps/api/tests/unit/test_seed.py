import os
import subprocess
import sys

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, func, select

from droidesk_api.core.config import Settings, get_settings
from droidesk_api.demo_tickets import DEMO_TICKETS
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.seed import main, seed_base_data
from droidesk_api.sla.enums import TargetUnit
from droidesk_api.sla.models import SlaPolicy
from droidesk_api.tickets.enums import Priority
from droidesk_api.tickets.models import Category, Ticket

EXAMPLE_TICKETS = len(DEMO_TICKETS)


def count(session: Session, model: type[User | Category | SlaPolicy | Ticket]) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def test_seeds_four_requesters_and_three_agents(session: Session) -> None:
    seed_base_data(session)
    users = session.exec(select(User).order_by(col(User.id))).all()
    assert [u.role for u in users] == [Role.REQUESTER] * 4 + [Role.AGENT] * 3


def test_seeded_users_have_droidesk_local_emails(session: Session) -> None:
    seed_base_data(session)
    assert all(u.email.endswith("@droidesk.local") for u in session.exec(select(User)))


def test_seeded_usernames_are_the_first_name_dot_surname(session: Session) -> None:
    seed_base_data(session)
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
    seed_base_data(session)
    users = session.exec(select(User))
    assert all(u.email == f"{u.username}@droidesk.local" for u in users)


def test_seeds_the_five_categories(session: Session) -> None:
    seed_base_data(session)
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
    seed_base_data(session)
    policy = session.get_one(SlaPolicy, priority)
    assert (policy.rank, policy.target_amount, policy.target_unit) == (
        rank,
        amount,
        unit,
    )


def test_seed_reports_that_it_loaded(session: Session) -> None:
    assert seed_base_data(session) is True


def test_seeding_twice_does_not_duplicate_anything(session: Session) -> None:
    seed_base_data(session)
    assert seed_base_data(session) is False
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
    assert seed_base_data(session) is False
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
    def test_demo_mode_loads_the_base_and_the_example_tickets(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_MODE", "demo")
        main()
        assert (count(session, User), count(session, Ticket)) == (
            7,
            EXAMPLE_TICKETS,
        )

    @pytest.mark.usefixtures("environment")
    def test_demo_is_the_mode_when_none_is_set(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.delenv("DROIDESK_MODE", raising=False)
        main()
        assert count(session, Ticket) == EXAMPLE_TICKETS

    @pytest.mark.usefixtures("environment")
    def test_empty_mode_loads_only_the_base(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_MODE", "empty")
        main()
        assert (
            count(session, User),
            count(session, Category),
            count(session, SlaPolicy),
            count(session, Ticket),
        ) == (7, 5, 4, 0)

    @pytest.mark.usefixtures("environment")
    def test_switching_to_demo_later_adds_the_tickets_to_the_base(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_MODE", "empty")
        main()
        monkeypatch.setenv("DROIDESK_MODE", "demo")
        get_settings.cache_clear()
        main()
        assert (count(session, User), count(session, Ticket)) == (
            7,
            EXAMPLE_TICKETS,
        )

    @pytest.mark.usefixtures("environment")
    def test_running_twice_keeps_the_data_once(
        self, monkeypatch: pytest.MonkeyPatch, session: Session
    ) -> None:
        monkeypatch.setenv("DROIDESK_MODE", "demo")
        main()
        main()
        assert (count(session, User), count(session, Ticket)) == (
            7,
            EXAMPLE_TICKETS,
        )

    @pytest.mark.usefixtures("environment")
    def test_demo_mode_reports_what_it_loaded_and_what_it_skipped(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("DROIDESK_MODE", "demo")
        with caplog.at_level("INFO"):
            main()
            main()
        assert [r.message for r in caplog.records] == [
            "Base cargada: usuarios, categorías y políticas de SLA.",
            "Modo demo: tickets de ejemplo cargados.",
            "Base omitida: la base de datos ya tiene datos.",
            "Modo demo: tickets de ejemplo omitidos, ya existen tickets.",
        ]

    @pytest.mark.usefixtures("environment")
    def test_empty_mode_reports_that_it_loads_no_tickets(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("DROIDESK_MODE", "empty")
        with caplog.at_level("INFO"):
            main()
        assert [r.message for r in caplog.records] == [
            "Base cargada: usuarios, categorías y políticas de SLA.",
            "Modo vacío: sin tickets de ejemplo.",
        ]


def test_runs_as_a_module_like_the_container_entrypoint(
    settings: Settings, engine: Engine, session: Session
) -> None:
    environment = {
        **os.environ,
        "DROIDESK_JWT_SECRET": settings.jwt_secret.get_secret_value(),
        "DROIDESK_DATABASE_URL": settings.database_url,
        "DROIDESK_MODE": "demo",
    }
    subprocess.run(
        [sys.executable, "-m", "droidesk_api.seed"], env=environment, check=True
    )
    assert (count(session, User), count(session, Ticket)) == (7, EXAMPLE_TICKETS)
