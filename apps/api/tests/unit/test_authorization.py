import pytest

from droidesk_api.core.errors import ForbiddenError, NotFoundError
from droidesk_api.identity.authorization import (
    ensure_can_view,
    require_agent,
    require_requester,
)
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from tests.factories import (
    AGENT_ID,
    OTHER_AGENT_ID,
    OTHER_REQUESTER_ID,
    REQUESTER_ID,
    make_ticket,
)

REQUESTER = User(
    id=REQUESTER_ID,
    username="ana",
    name="Ana Rojas",
    email="ana@droidesk.local",
    role=Role.REQUESTER,
)
OTHER_REQUESTER = User(
    id=OTHER_REQUESTER_ID,
    username="bruno",
    name="Bruno",
    email="bruno@droidesk.local",
    role=Role.REQUESTER,
)
AGENT = User(
    id=AGENT_ID,
    username="elena",
    name="Elena Vidal",
    email="elena@droidesk.local",
    role=Role.AGENT,
)
OTHER_AGENT = User(
    id=OTHER_AGENT_ID,
    username="felipe",
    name="Felipe",
    email="felipe@droidesk.local",
    role=Role.AGENT,
)


def test_requester_guard_lets_a_requester_through() -> None:
    assert require_requester(REQUESTER) is REQUESTER


def test_requester_guard_forbids_an_agent() -> None:
    with pytest.raises(ForbiddenError):
        require_requester(AGENT)


def test_agent_guard_lets_an_agent_through() -> None:
    assert require_agent(AGENT) is AGENT


def test_agent_guard_forbids_a_requester() -> None:
    with pytest.raises(ForbiddenError):
        require_agent(REQUESTER)


def test_requester_can_view_their_own_ticket() -> None:
    ensure_can_view(REQUESTER, make_ticket(requester_id=REQUESTER_ID))


def test_requester_cannot_view_a_foreign_ticket_as_if_it_did_not_exist() -> None:
    with pytest.raises(NotFoundError):
        ensure_can_view(OTHER_REQUESTER, make_ticket(requester_id=REQUESTER_ID))


@pytest.mark.parametrize("agent", [AGENT, OTHER_AGENT])
def test_any_agent_can_view_any_ticket(agent: User) -> None:
    ensure_can_view(agent, make_ticket(requester_id=REQUESTER_ID, assignee_id=AGENT_ID))
