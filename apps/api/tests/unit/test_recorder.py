from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest
from sqlmodel import Session

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import NewEvent, list_events, record_event
from droidesk_api.tickets.models import Comment
from tests.factories import AGENT_ID, CREATED_AT, REQUESTER_ID, add_ticket


@pytest.fixture
def ticket_id(session: Session, demo_data: None) -> int:
    ticket = add_ticket(session)
    assert ticket.id is not None
    return ticket.id


def event(
    ticket_id: int, kind: EventKind = EventKind.CREATED, **changes: Any
) -> NewEvent:
    base = NewEvent(
        ticket_id=ticket_id, actor_id=REQUESTER_ID, kind=kind, created_at=CREATED_AT
    )
    return replace(base, **changes)


def test_recorded_event_gets_an_id(session: Session, ticket_id: int) -> None:
    assert record_event(session, event(ticket_id)).id is not None


def test_recorded_event_keeps_who_and_what(session: Session, ticket_id: int) -> None:
    recorded = record_event(
        session, event(ticket_id, EventKind.ASSIGNED, actor_id=AGENT_ID)
    )
    assert (recorded.ticket_id, recorded.actor_id, recorded.kind) == (
        ticket_id,
        AGENT_ID,
        EventKind.ASSIGNED,
    )


def test_recorded_event_keeps_the_previous_and_new_values(
    session: Session, ticket_id: int
) -> None:
    recorded = record_event(
        session,
        event(
            ticket_id,
            EventKind.STATUS_CHANGED,
            from_value="open",
            to_value="in_progress",
        ),
    )
    assert (recorded.from_value, recorded.to_value) == ("open", "in_progress")


def test_values_are_optional(session: Session, ticket_id: int) -> None:
    recorded = record_event(session, event(ticket_id))
    assert (recorded.from_value, recorded.to_value) == (None, None)


def test_the_comment_link_is_optional(session: Session, ticket_id: int) -> None:
    assert record_event(session, event(ticket_id)).comment_id is None


def test_a_commented_event_keeps_the_link_to_its_comment(
    session: Session, ticket_id: int
) -> None:
    comment = Comment(
        ticket_id=ticket_id, author_id=REQUESTER_ID, body="Hola", created_at=CREATED_AT
    )
    session.add(comment)
    session.flush()
    recorded = record_event(
        session, event(ticket_id, EventKind.COMMENTED, comment_id=comment.id)
    )
    assert recorded.comment_id == comment.id


def test_recording_does_not_commit(session: Session, ticket_id: int) -> None:
    record_event(session, event(ticket_id))
    session.rollback()
    assert list_events(session, ticket_id) == []


def test_recording_joins_the_callers_transaction(
    session: Session, ticket_id: int
) -> None:
    record_event(session, event(ticket_id))
    session.commit()
    assert len(list_events(session, ticket_id)) == 1


def test_events_are_listed_in_chronological_order(
    session: Session, ticket_id: int
) -> None:
    later = record_event(
        session,
        event(
            ticket_id,
            EventKind.STATUS_CHANGED,
            created_at=CREATED_AT + timedelta(hours=1),
        ),
    )
    earlier = record_event(session, event(ticket_id, EventKind.CREATED))
    assert [e.id for e in list_events(session, ticket_id)] == [earlier.id, later.id]


def test_events_with_the_same_instant_keep_the_order_they_were_recorded(
    session: Session, ticket_id: int
) -> None:
    first = record_event(session, event(ticket_id, EventKind.ASSIGNED))
    second = record_event(session, event(ticket_id, EventKind.STATUS_CHANGED))
    assert [e.id for e in list_events(session, ticket_id)] == [first.id, second.id]


def test_only_the_events_of_that_ticket_are_listed(
    session: Session, ticket_id: int
) -> None:
    other = add_ticket(session)
    assert other.id is not None
    record_event(session, event(other.id))
    assert list_events(session, ticket_id) == []
