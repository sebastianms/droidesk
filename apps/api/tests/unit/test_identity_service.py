import pytest
from sqlalchemy import Engine, event
from sqlmodel import Session, func, select

from droidesk_api.core.errors import NotAuthenticatedError
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.identity.service import (
    UNKNOWN_USER_MESSAGE,
    authenticate,
    list_demo_users,
    users_by_id,
)


def user_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(User)).one()


def add_user(session: Session, name: str, role: Role) -> None:
    username = name.lower()
    session.add(
        User(
            username=username,
            name=name,
            email=f"{username}@droidesk.local",
            role=role,
        )
    )
    session.commit()


@pytest.mark.usefixtures("demo_data")
class TestAuthenticate:
    def test_an_existing_username_returns_its_user(self, session: Session) -> None:
        assert authenticate(session, "ana.rojas").id == 1

    def test_the_user_keeps_the_role_it_has_stored(self, session: Session) -> None:
        assert authenticate(session, "elena.vidal").role == Role.AGENT

    def test_an_unknown_username_is_not_authenticated(self, session: Session) -> None:
        with pytest.raises(NotAuthenticatedError) as error:
            authenticate(session, "desconocido")
        assert error.value.message == UNKNOWN_USER_MESSAGE

    def test_the_message_points_to_the_demo_users(self) -> None:
        assert UNKNOWN_USER_MESSAGE == (
            "El usuario no existe. Revisa los usuarios de demo en el ícono ?."
        )

    def test_an_unknown_username_creates_nobody(self, session: Session) -> None:
        with pytest.raises(NotAuthenticatedError):
            authenticate(session, "desconocido")
        assert user_count(session) == 7

    @pytest.mark.parametrize("username", ["ANA.ROJAS", " ana.rojas", ""])
    def test_the_username_is_matched_as_given(
        self, session: Session, username: str
    ) -> None:
        with pytest.raises(NotAuthenticatedError):
            authenticate(session, username)


class TestListDemoUsers:
    def test_there_is_nobody_in_an_empty_database(self, session: Session) -> None:
        assert list_demo_users(session) == []

    @pytest.mark.usefixtures("demo_data")
    def test_lists_the_seeded_users_requesters_first(self, session: Session) -> None:
        assert [user.username for user in list_demo_users(session)] == [
            "ana.rojas",
            "bruno.castillo",
            "carla.mena",
            "diego.fuentes",
            "elena.vidal",
            "felipe.araya",
            "gabriela.soto",
        ]

    def test_orders_by_role_before_name(self, session: Session) -> None:
        add_user(session, "Ana", Role.AGENT)
        add_user(session, "Zoe", Role.REQUESTER)
        assert [user.name for user in list_demo_users(session)] == ["Zoe", "Ana"]

    def test_orders_by_name_ignoring_case_within_a_role(self, session: Session) -> None:
        add_user(session, "bruno", Role.REQUESTER)
        add_user(session, "Carla", Role.REQUESTER)
        add_user(session, "Ana", Role.REQUESTER)
        assert [user.name for user in list_demo_users(session)] == [
            "Ana",
            "bruno",
            "Carla",
        ]


class TestUsersById:
    @pytest.mark.usefixtures("demo_data")
    def test_returns_the_requested_users_keyed_by_id(self, session: Session) -> None:
        found = users_by_id(session, [1, 5, 1])
        assert {id_: user.username for id_, user in found.items()} == {
            1: "ana.rojas",
            5: "elena.vidal",
        }

    @pytest.mark.usefixtures("demo_data")
    def test_ignores_ids_that_do_not_exist(self, session: Session) -> None:
        assert list(users_by_id(session, [1, 999])) == [1]

    def test_asking_for_nobody_does_not_query(self, engine: Engine) -> None:
        statements: list[str] = []
        event.listen(
            engine, "before_cursor_execute", lambda *args: statements.append(args[2])
        )
        with Session(engine) as session:
            assert users_by_id(session, []) == {}
        assert statements == []
