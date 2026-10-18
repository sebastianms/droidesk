import pytest

from droidesk_api.core.errors import ForbiddenError
from droidesk_api.identity.authorization import require_agent, require_requester
from droidesk_api.identity.enums import Role
from tests.factories import AGENT_ID, REQUESTER_ID, make_user

REQUESTER = make_user(REQUESTER_ID, Role.REQUESTER)
AGENT = make_user(AGENT_ID, Role.AGENT)


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
