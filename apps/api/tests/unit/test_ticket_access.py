import pytest

from droidesk_api.core.errors import NotFoundError
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.tickets.access import ensure_can_view
from tests.factories import (
    AGENT_ID,
    OTHER_AGENT_ID,
    OTHER_REQUESTER_ID,
    REQUESTER_ID,
    make_ticket,
    make_user,
)

REQUESTER = make_user(REQUESTER_ID, Role.REQUESTER)
OTHER_REQUESTER = make_user(OTHER_REQUESTER_ID, Role.REQUESTER)


def test_requester_can_view_their_own_ticket() -> None:
    ensure_can_view(REQUESTER, make_ticket(requester_id=REQUESTER_ID))


def test_requester_cannot_view_a_foreign_ticket_as_if_it_did_not_exist() -> None:
    with pytest.raises(NotFoundError):
        ensure_can_view(OTHER_REQUESTER, make_ticket(requester_id=REQUESTER_ID))


@pytest.mark.parametrize(
    "agent", [make_user(AGENT_ID, Role.AGENT), make_user(OTHER_AGENT_ID, Role.AGENT)]
)
def test_any_agent_can_view_any_ticket(agent: User) -> None:
    ensure_can_view(agent, make_ticket(requester_id=REQUESTER_ID, assignee_id=AGENT_ID))
