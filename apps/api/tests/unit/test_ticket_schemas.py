from typing import get_args

import pytest
from pydantic import ValidationError

from droidesk_api.tickets.lifecycle import TRANSITIONS, TicketAction
from droidesk_api.tickets.schemas import StateAction, TicketCreate, TransitionRequest


def test_transition_requests_accept_exactly_the_actions_of_the_lifecycle() -> None:
    assert set(get_args(StateAction)) == {t.action for t in TRANSITIONS}


def test_a_transition_request_reads_the_action_by_its_code() -> None:
    assert (
        TransitionRequest.model_validate({"action": "cancel"}).action
        == TicketAction.CANCEL
    )


def test_a_new_ticket_defaults_to_medium_priority() -> None:
    ticket = TicketCreate(title="Título", description="Detalle", category_id=1)
    assert ticket.priority == "medium"


@pytest.mark.parametrize("text", ["", " ", "\n\t "])
def test_a_blank_title_is_invalid(text: str) -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        TicketCreate(title=text, description="Detalle", category_id=1)


def test_inner_spaces_and_line_breaks_are_kept() -> None:
    ticket = TicketCreate(
        title=" Dos  palabras ", description=" Línea 1\n  Línea 2 ", category_id=1
    )
    assert (ticket.title, ticket.description) == (
        "Dos  palabras",
        "Línea 1\n  Línea 2",
    )
