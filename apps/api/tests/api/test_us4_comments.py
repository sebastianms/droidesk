from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine, event
from sqlmodel import Session, col, select

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.models import TicketEvent
from droidesk_api.audit.recorder import list_events
from droidesk_api.core.db import persisted_id
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.models import Comment
from tests.api.helpers import (
    NOT_FOUND,
    TICKETS_URL,
    Act,
    LoginAs,
    PostComment,
    PostReply,
    Read,
    add_ticket_id,
    add_ticket_in_id,
    comments_url,
    post_ticket,
    published_operations,
    reload,
)
from tests.factories import (
    AGENT_ID,
    AGENT_USERNAME,
    CREATED_AT,
    OTHER_AGENT_ID,
    OTHER_AGENT_USERNAME,
    OTHER_REQUESTER_ID,
    OTHER_REQUESTER_USERNAME,
    REQUESTER_ID,
    REQUESTER_USERNAME,
)
from tests.fakes import FakeClock

HOUR = timedelta(hours=1)
BODY = "¿Puedes revisar si el problema sigue ocurriendo?"
HIGH_DEADLINE = "2026-10-20T13:05:00Z"  # martes 10:05 local
NOT_COMMENTABLE = [TicketStatus.CLOSED, TicketStatus.CANCELLED]
COMMENTABLE = [
    TicketStatus.OPEN,
    TicketStatus.IN_PROGRESS,
    TicketStatus.ON_HOLD,
    TicketStatus.RESOLVED,
]
Trail = list[tuple[EventKind, int, str | None, str | None]]
Listing = Callable[[str, str], Response]
# Cada vista con el perfil que puede pedirla.
LISTINGS = [
    (REQUESTER_USERNAME, "mine"),
    (AGENT_USERNAME, "queue"),
    (AGENT_USERNAME, "assigned"),
]


def comments_of(response: Response) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = response.json()["comments"]
    return comments


def event_trail(session: Session, ticket_id: int) -> Trail:
    return [
        (row.kind, row.actor_id, row.from_value, row.to_value)
        for row in list_events(session, ticket_id)
    ]


def stored_comments(session: Session, ticket_id: int) -> list[Comment]:
    session.expire_all()
    statement = select(Comment).where(col(Comment.ticket_id) == ticket_id)
    return list(session.exec(statement))


def add_comments(session: Session, ticket_id: int, amount: int) -> None:
    for number in range(amount):
        session.add(
            Comment(
                ticket_id=ticket_id,
                author_id=AGENT_ID,
                body=f"Comentario {number}",
                created_at=CREATED_AT,
            )
        )
    session.commit()


def counts_of(response: Response) -> dict[int, int]:
    return {ticket["id"]: ticket["comment_count"] for ticket in response.json()}


def error_of(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


@pytest.mark.usefixtures("demo_data")
class TestWhoCanComment:
    @pytest.mark.parametrize(
        ("username", "author_id", "author_name"),
        [
            (REQUESTER_USERNAME, REQUESTER_ID, "Ana Rojas"),
            (AGENT_USERNAME, AGENT_ID, "Elena Vidal"),
            (OTHER_AGENT_USERNAME, OTHER_AGENT_ID, "Felipe Araya"),
        ],
    )
    def test_the_owner_and_any_agent_can_comment(
        self,
        comment: PostComment,
        session: Session,
        username: str,
        author_id: int,
        author_name: str,
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        response = comment(username, ticket_id, BODY)
        assert (response.status_code, comments_of(response)) == (
            201,
            [
                {
                    "id": 1,
                    "author": {"id": author_id, "name": author_name},
                    "body": BODY,
                    "created_at": "2026-10-19T13:05:00Z",
                    "reply_to_id": None,
                }
            ],
        )

    def test_an_agent_who_has_not_taken_the_ticket_can_comment(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        assert comment(OTHER_AGENT_USERNAME, ticket_id, BODY).status_code == 201

    @pytest.mark.parametrize("status", COMMENTABLE)
    @pytest.mark.parametrize("username", [REQUESTER_USERNAME, AGENT_USERNAME])
    def test_any_status_that_is_not_final_accepts_comments(
        self,
        comment: PostComment,
        session: Session,
        status: TicketStatus,
        username: str,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert comment(username, ticket_id, BODY).status_code == 201

    def test_answers_with_the_updated_ticket_detail(
        self, comment: PostComment, read: Read, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        answered = comment(AGENT_USERNAME, ticket_id, BODY)
        assert answered.json() == read(AGENT_USERNAME, ticket_id).json()

    def test_a_comment_from_an_agent_does_not_change_the_status(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.RESOLVED)
        assert comment(AGENT_USERNAME, ticket_id, BODY).json()["status"] == "resolved"

    def test_a_comment_from_the_owner_on_a_resolved_ticket_does_not_reopen_it(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.RESOLVED)
        assert comment(REQUESTER_USERNAME, ticket_id, BODY).json()["status"] == (
            "resolved"
        )

    def test_a_comment_leaves_the_ticket_row_untouched(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        before = reload(session, ticket_id).model_dump()
        comment(REQUESTER_USERNAME, ticket_id, BODY)
        assert reload(session, ticket_id).model_dump() == before

    def test_the_comment_carries_the_instant_it_was_made(
        self, comment: PostComment, session: Session, clock: FakeClock
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        clock.advance(2 * HOUR)
        response = comment(REQUESTER_USERNAME, ticket_id, BODY)
        assert comments_of(response)[0]["created_at"] == "2026-10-19T15:05:00Z"

    def test_a_new_ticket_has_no_comments(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        created = post_ticket(client, login_as(REQUESTER_USERNAME))
        assert comments_of(created) == []


@pytest.mark.usefixtures("demo_data")
class TestBody:
    @pytest.mark.parametrize(
        ("sent", "kept"),
        [
            ("  Hola  ", "Hola"),
            ("\n\tHola\n", "Hola"),
            ("Primera línea\n\n  Segunda línea", "Primera línea\n\n  Segunda línea"),
        ],
    )
    def test_trims_the_edges_and_keeps_the_inner_text(
        self, comment: PostComment, session: Session, sent: str, kept: str
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        assert comments_of(comment(AGENT_USERNAME, ticket_id, sent))[0]["body"] == kept

    def test_markup_is_kept_as_plain_text(
        self, comment: PostComment, session: Session
    ) -> None:
        text = '<img src=x onerror="alert(1)"> &amp; <b>negrita</b>'
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        assert comments_of(comment(AGENT_USERNAME, ticket_id, text))[0]["body"] == text

    @pytest.mark.parametrize("sent", ["", " ", "\n\t "])
    def test_rejects_an_empty_or_blank_comment(
        self, comment: PostComment, session: Session, sent: str
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        response = comment(AGENT_USERNAME, ticket_id, sent)
        assert (response.status_code, response.json()["detail"][0]["loc"]) == (
            422,
            ["body", "body"],
        )

    @pytest.mark.parametrize("letter", ["a", "ñ", "😀"])
    def test_accepts_2000_characters_and_rejects_2001(
        self, comment: PostComment, session: Session, letter: str
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        statuses = [
            comment(AGENT_USERNAME, ticket_id, letter * length).status_code
            for length in (2000, 2001)
        ]
        assert statuses == [201, 422]

    def test_the_length_counts_after_trimming(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        padded = f"  {'a' * 2000}  "
        assert comment(AGENT_USERNAME, ticket_id, padded).status_code == 201

    def test_a_rejected_comment_leaves_no_trace(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.ON_HOLD)
        comment(REQUESTER_USERNAME, ticket_id, " ")
        assert (
            stored_comments(session, ticket_id),
            list_events(session, ticket_id),
            reload(session, ticket_id).status,
        ) == ([], [], TicketStatus.ON_HOLD)

    def test_rejects_a_request_without_a_body(
        self, client: TestClient, login_as: LoginAs, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        response = client.post(
            comments_url(ticket_id), headers=login_as(AGENT_USERNAME), json={}
        )
        assert response.status_code == 422


@pytest.mark.usefixtures("demo_data")
class TestRestrictions:
    @pytest.mark.parametrize("status", NOT_COMMENTABLE)
    @pytest.mark.parametrize("username", [REQUESTER_USERNAME, AGENT_USERNAME])
    def test_a_final_ticket_answers_409(
        self,
        comment: PostComment,
        session: Session,
        status: TicketStatus,
        username: str,
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert error_of(comment(username, ticket_id, BODY)) == (
            409,
            "action_not_allowed",
        )

    def test_the_conflict_says_which_status_blocks_it(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.CLOSED)
        assert comment(AGENT_USERNAME, ticket_id, BODY).json()["message"] == (
            "La acción «Comentar» no está disponible con el ticket en estado «Cerrado»."
        )

    @pytest.mark.parametrize("status", NOT_COMMENTABLE)
    def test_a_final_ticket_keeps_no_new_comment_or_event(
        self, comment: PostComment, session: Session, status: TicketStatus
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        comment(AGENT_USERNAME, ticket_id, BODY)
        assert (
            stored_comments(session, ticket_id),
            list_events(session, ticket_id),
        ) == ([], [])

    def test_another_requester_gets_not_found(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        response = comment(OTHER_REQUESTER_USERNAME, ticket_id, BODY)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    @pytest.mark.parametrize("status", [*COMMENTABLE, *NOT_COMMENTABLE])
    def test_another_requester_never_learns_the_status(
        self, comment: PostComment, session: Session, status: TicketStatus
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        assert error_of(comment(OTHER_REQUESTER_USERNAME, ticket_id, BODY)) == (
            404,
            "not_found",
        )

    def test_another_requester_leaves_no_comment(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.ON_HOLD)
        comment(OTHER_REQUESTER_USERNAME, ticket_id, BODY)
        assert (
            stored_comments(session, ticket_id),
            reload(session, ticket_id).status,
        ) == ([], TicketStatus.ON_HOLD)

    @pytest.mark.parametrize("username", [REQUESTER_USERNAME, AGENT_USERNAME])
    def test_an_unknown_ticket_answers_404(
        self, comment: PostComment, username: str
    ) -> None:
        assert error_of(comment(username, 999, BODY)) == (404, "not_found")

    def test_without_a_token_answers_401(
        self, client: TestClient, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        response = client.post(comments_url(ticket_id), json={"body": BODY})
        assert error_of(response) == (401, "not_authenticated")

    def test_with_an_invalid_token_answers_401(
        self, client: TestClient, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        response = client.post(
            comments_url(ticket_id),
            headers={"Authorization": "Bearer not-a-token"},
            json={"body": BODY},
        )
        assert error_of(response) == (401, "not_authenticated")


@pytest.mark.usefixtures("demo_data")
class TestReplies:
    @pytest.fixture
    def ticket_id(self, session: Session) -> int:
        return add_ticket_in_id(session, TicketStatus.IN_PROGRESS)

    @pytest.fixture
    def original_id(self, comment: PostComment, ticket_id: int) -> int:
        original: int = comments_of(comment(AGENT_USERNAME, ticket_id, BODY))[0]["id"]
        return original

    @pytest.mark.parametrize("username", [REQUESTER_USERNAME, OTHER_AGENT_USERNAME])
    def test_a_comment_can_cite_another_of_the_same_ticket(
        self, reply: PostReply, ticket_id: int, original_id: int, username: str
    ) -> None:
        response = reply(username, ticket_id, "Sí, sigue igual", original_id)
        assert (response.status_code, comments_of(response)[-1]["reply_to_id"]) == (
            201,
            original_id,
        )

    def test_the_detail_keeps_the_link_to_the_original(
        self, read: Read, reply: PostReply, ticket_id: int, original_id: int
    ) -> None:
        reply(REQUESTER_USERNAME, ticket_id, "Sí, sigue igual", original_id)
        links = [c["reply_to_id"] for c in comments_of(read(AGENT_USERNAME, ticket_id))]
        assert links == [None, original_id]

    def test_a_reply_can_cite_another_reply(
        self, reply: PostReply, ticket_id: int, original_id: int
    ) -> None:
        first = reply(REQUESTER_USERNAME, ticket_id, "Primera", original_id)
        first_id = comments_of(first)[-1]["id"]
        second = reply(AGENT_USERNAME, ticket_id, "Segunda", first_id)
        assert comments_of(second)[-1]["reply_to_id"] == first_id

    def test_a_comment_without_a_reply_has_no_link(
        self, comment: PostComment, ticket_id: int
    ) -> None:
        response = comment(AGENT_USERNAME, ticket_id, BODY)
        assert comments_of(response)[-1]["reply_to_id"] is None

    def test_an_explicit_null_is_the_same_as_no_reply(
        self, reply: PostReply, ticket_id: int
    ) -> None:
        response = reply(AGENT_USERNAME, ticket_id, BODY, None)
        assert (response.status_code, comments_of(response)[-1]["reply_to_id"]) == (
            201,
            None,
        )

    def test_the_reply_is_stored_with_its_original(
        self, reply: PostReply, session: Session, ticket_id: int, original_id: int
    ) -> None:
        reply(REQUESTER_USERNAME, ticket_id, "Sí, sigue igual", original_id)
        stored = stored_comments(session, ticket_id)
        assert [c.reply_to_id for c in stored] == [None, original_id]

    def test_a_comment_that_does_not_exist_is_rejected_with_422_on_its_field(
        self, reply: PostReply, ticket_id: int
    ) -> None:
        response = reply(AGENT_USERNAME, ticket_id, BODY, 999)
        assert (response.status_code, response.json()["detail"][0]["loc"]) == (
            422,
            ["body", "reply_to_id"],
        )

    @pytest.fixture
    def foreign_id(self, session: Session) -> int:
        """Un comentario que existe, pero en otro ticket."""
        elsewhere = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        add_comments(session, elsewhere, 1)
        return persisted_id(stored_comments(session, elsewhere)[0])

    def test_a_comment_of_another_ticket_is_rejected_with_422_on_its_field(
        self, reply: PostReply, ticket_id: int, foreign_id: int
    ) -> None:
        response = reply(AGENT_USERNAME, ticket_id, BODY, foreign_id)
        assert (response.status_code, response.json()["detail"][0]["loc"]) == (
            422,
            ["body", "reply_to_id"],
        )

    def test_a_foreign_comment_answers_exactly_like_one_that_does_not_exist(
        self, reply: PostReply, ticket_id: int, foreign_id: int
    ) -> None:
        foreign = reply(AGENT_USERNAME, ticket_id, BODY, foreign_id)
        missing = reply(AGENT_USERNAME, ticket_id, BODY, foreign_id + 100)
        assert foreign.json() == missing.json()

    def test_the_rejection_explains_what_failed(
        self, reply: PostReply, ticket_id: int
    ) -> None:
        response = reply(AGENT_USERNAME, ticket_id, BODY, 999)
        assert response.json()["detail"][0]["msg"] == (
            "El comentario al que respondes no existe en este ticket."
        )

    def test_a_reply_that_is_not_a_number_is_rejected_with_422(
        self, client: TestClient, login_as: LoginAs, ticket_id: int
    ) -> None:
        response = client.post(
            comments_url(ticket_id),
            headers=login_as(AGENT_USERNAME),
            json={"body": BODY, "reply_to_id": "abc"},
        )
        assert (response.status_code, response.json()["detail"][0]["loc"]) == (
            422,
            ["body", "reply_to_id"],
        )

    def test_a_rejected_reply_leaves_no_comment_or_event(
        self, reply: PostReply, session: Session, ticket_id: int
    ) -> None:
        reply(AGENT_USERNAME, ticket_id, BODY, 999)
        assert (
            stored_comments(session, ticket_id),
            list_events(session, ticket_id),
        ) == ([], [])

    def test_a_rejected_reply_does_not_resume_a_ticket_on_hold(
        self, reply: PostReply, session: Session
    ) -> None:
        held = add_ticket_in_id(session, TicketStatus.ON_HOLD)
        before = reload(session, held).model_dump()
        reply(REQUESTER_USERNAME, held, BODY, 999)
        assert (
            reload(session, held).model_dump(),
            stored_comments(session, held),
            list_events(session, held),
        ) == (before, [], [])

    def test_an_accepted_reply_does_resume_a_ticket_on_hold(
        self, reply: PostReply, session: Session
    ) -> None:
        held = add_ticket_in_id(session, TicketStatus.ON_HOLD)
        add_comments(session, held, 1)
        original = persisted_id(stored_comments(session, held)[0])
        response = reply(REQUESTER_USERNAME, held, BODY, original)
        assert response.json()["status"] == "in_progress"

    def test_a_final_ticket_is_still_a_conflict_before_the_reply_is_checked(
        self, reply: PostReply, session: Session
    ) -> None:
        closed = add_ticket_in_id(session, TicketStatus.CLOSED)
        assert error_of(reply(AGENT_USERNAME, closed, BODY, 999)) == (
            409,
            "action_not_allowed",
        )

    def test_another_requester_still_gets_not_found(
        self, reply: PostReply, ticket_id: int, original_id: int
    ) -> None:
        response = reply(OTHER_REQUESTER_USERNAME, ticket_id, BODY, original_id)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)


@pytest.mark.usefixtures("demo_data")
class TestHistory:
    def test_a_comment_is_recorded_in_the_history_with_its_author(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        comment(REQUESTER_USERNAME, ticket_id, BODY)
        assert event_trail(session, ticket_id) == [
            (EventKind.COMMENTED, REQUESTER_ID, None, None)
        ]

    def test_the_event_points_to_its_comment(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        comment(AGENT_USERNAME, ticket_id, BODY)
        (recorded,) = list_events(session, ticket_id)
        (stored,) = stored_comments(session, ticket_id)
        assert (recorded.comment_id, recorded.created_at) == (
            stored.id,
            stored.created_at,
        )

    def test_the_timeline_shows_the_comment_without_repeating_its_text(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        response = comment(AGENT_USERNAME, ticket_id, BODY)
        assert response.json()["history"] == [
            {
                "id": 1,
                "kind": "commented",
                "actor": {"id": AGENT_ID, "name": "Elena Vidal"},
                "from_value": None,
                "to_value": None,
                "created_at": "2026-10-19T13:05:00Z",
            }
        ]

    def test_only_comments_carry_a_comment_id(
        self, act: Act, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        act(AGENT_USERNAME, ticket_id, "take")
        comment(AGENT_USERNAME, ticket_id, BODY)
        events = session.exec(select(TicketEvent).order_by(col(TicketEvent.id)))
        assert [(row.kind, row.comment_id) for row in events] == [
            (EventKind.ASSIGNED, None),
            (EventKind.STATUS_CHANGED, None),
            (EventKind.COMMENTED, 1),
        ]


@pytest.mark.usefixtures("demo_data")
class TestRequesterReplyOnHold:
    @pytest.fixture
    def ticket_id(self, act: Act, client: TestClient, login_as: LoginAs) -> int:
        """Prioridad alta creada el lunes 10:05 y tomada por Elena, que vence el martes 10:05."""
        created = post_ticket(client, login_as(REQUESTER_USERNAME), priority="high")
        ticket_id: int = created.json()["id"]
        act(AGENT_USERNAME, ticket_id, "take")
        return ticket_id

    @pytest.fixture
    def held(self, act: Act, clock: FakeClock, ticket_id: int) -> int:
        """En espera desde las 11:05 y con 4 horas hábiles transcurridas a las 15:05."""
        clock.advance(HOUR)
        act(AGENT_USERNAME, ticket_id, "hold")
        clock.advance(4 * HOUR)
        return ticket_id

    def test_the_ticket_returns_to_in_progress_with_its_agent(
        self, comment: PostComment, held: int
    ) -> None:
        ticket = comment(REQUESTER_USERNAME, held, BODY).json()
        assert (ticket["status"], ticket["assignee"]["id"]) == ("in_progress", AGENT_ID)

    def test_records_the_comment_and_then_the_status_change_in_the_requesters_name(
        self, comment: PostComment, session: Session, held: int
    ) -> None:
        comment(REQUESTER_USERNAME, held, BODY)
        assert event_trail(session, held)[-2:] == [
            (EventKind.COMMENTED, REQUESTER_ID, None, None),
            (EventKind.STATUS_CHANGED, REQUESTER_ID, "on_hold", "in_progress"),
        ]

    def test_both_events_share_the_instant_of_the_comment(
        self, comment: PostComment, session: Session, clock: FakeClock, held: int
    ) -> None:
        comment(REQUESTER_USERNAME, held, BODY)
        assert {row.created_at for row in list_events(session, held)[-2:]} == {
            clock.now()
        }

    def test_the_history_shows_the_change_to_the_requester(
        self, comment: PostComment, held: int
    ) -> None:
        history = comment(REQUESTER_USERNAME, held, BODY).json()["history"]
        assert [(e["kind"], e["actor"]["name"]) for e in history[-2:]] == [
            ("commented", "Ana Rojas"),
            ("status_changed", "Ana Rojas"),
        ]

    def test_resumes_the_deadline_pushed_by_the_paused_business_time(
        self, comment: PostComment, held: int
    ) -> None:
        response = comment(REQUESTER_USERNAME, held, BODY)
        assert response.json()["sla"] == {
            "state": "on_track",
            "due_at": "2026-10-20T17:05:00Z",  # martes 14:05 local
        }

    def test_stores_the_paused_minutes_and_clears_the_wait(
        self, comment: PostComment, session: Session, held: int
    ) -> None:
        comment(REQUESTER_USERNAME, held, BODY)
        ticket = reload(session, held)
        assert (ticket.sla_paused_minutes, ticket.on_hold_since) == (240, None)

    def test_the_sla_was_paused_until_the_reply(
        self, comment: PostComment, read: Read, held: int
    ) -> None:
        paused = read(REQUESTER_USERNAME, held).json()["sla"]
        resumed = comment(REQUESTER_USERNAME, held, BODY).json()["sla"]["state"]
        assert (paused, resumed) == ({"state": "paused", "due_at": None}, "on_track")

    def test_a_wait_begun_after_the_deadline_does_not_move_it(
        self,
        act: Act,
        comment: PostComment,
        session: Session,
        clock: FakeClock,
        ticket_id: int,
    ) -> None:
        clock.advance(25 * HOUR)  # martes 11:05 local, ya vencido
        act(AGENT_USERNAME, ticket_id, "hold")
        clock.advance(2 * HOUR)
        response = comment(REQUESTER_USERNAME, ticket_id, BODY)
        assert (
            reload(session, ticket_id).sla_paused_minutes,
            response.json()["sla"],
        ) == (
            0,
            {"state": "breached", "due_at": HIGH_DEADLINE},
        )

    def test_the_requester_keeps_only_the_comment_action(
        self, comment: PostComment, held: int
    ) -> None:
        response = comment(REQUESTER_USERNAME, held, BODY)
        assert response.json()["allowed_actions"] == ["comment"]

    def test_the_agent_gets_the_hold_action_back(
        self, act: Act, comment: PostComment, read: Read, held: int
    ) -> None:
        comment(REQUESTER_USERNAME, held, BODY)
        assert read(AGENT_USERNAME, held).json()["allowed_actions"] == [
            "hold",
            "resolve",
            "comment",
            "change_priority",
        ]

    def test_a_second_comment_does_not_move_the_ticket_again(
        self, comment: PostComment, session: Session, held: int
    ) -> None:
        comment(REQUESTER_USERNAME, held, BODY)
        comment(REQUESTER_USERNAME, held, "Gracias")
        kinds = [row.kind for row in list_events(session, held)[-3:]]
        assert kinds == [
            EventKind.COMMENTED,
            EventKind.STATUS_CHANGED,
            EventKind.COMMENTED,
        ]

    @pytest.mark.parametrize("status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
    def test_outside_the_wait_a_requester_comment_changes_no_status(
        self, comment: PostComment, session: Session, status: TicketStatus
    ) -> None:
        ticket_id = add_ticket_in_id(session, status)
        comment(REQUESTER_USERNAME, ticket_id, BODY)
        assert [row.kind for row in list_events(session, ticket_id)] == [
            EventKind.COMMENTED
        ]


@pytest.mark.usefixtures("demo_data")
class TestAgentCommentOnHold:
    @pytest.fixture
    def held(self, session: Session) -> int:
        return add_ticket_in_id(session, TicketStatus.ON_HOLD)

    @pytest.mark.parametrize("username", [AGENT_USERNAME, OTHER_AGENT_USERNAME])
    def test_the_ticket_stays_on_hold(
        self, comment: PostComment, held: int, username: str
    ) -> None:
        response = comment(username, held, BODY)
        assert (response.json()["status"], response.json()["sla"]["state"]) == (
            "on_hold",
            "paused",
        )

    def test_only_the_comment_is_recorded(
        self, comment: PostComment, session: Session, held: int
    ) -> None:
        comment(AGENT_USERNAME, held, BODY)
        assert event_trail(session, held) == [
            (EventKind.COMMENTED, AGENT_ID, None, None)
        ]

    def test_the_wait_keeps_running(
        self, comment: PostComment, session: Session, held: int
    ) -> None:
        before = reload(session, held).model_dump()
        comment(AGENT_USERNAME, held, BODY)
        assert reload(session, held).model_dump() == before
        assert before["on_hold_since"] == CREATED_AT


@pytest.mark.usefixtures("demo_data")
class TestDetail:
    @pytest.fixture
    def conversation(
        self, comment: PostComment, session: Session, clock: FakeClock
    ) -> int:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        for username, body in (
            (REQUESTER_USERNAME, "Primero"),
            (AGENT_USERNAME, "Segundo"),
            (OTHER_AGENT_USERNAME, "Tercero"),
            (REQUESTER_USERNAME, "Cuarto"),
        ):
            clock.advance(HOUR)
            comment(username, ticket_id, body)
        return ticket_id

    def test_lists_the_comments_in_chronological_order_with_their_authors(
        self, read: Read, conversation: int
    ) -> None:
        comments = comments_of(read(AGENT_USERNAME, conversation))
        assert [(c["body"], c["author"]["name"]) for c in comments] == [
            ("Primero", "Ana Rojas"),
            ("Segundo", "Elena Vidal"),
            ("Tercero", "Felipe Araya"),
            ("Cuarto", "Ana Rojas"),
        ]

    def test_each_comment_has_its_own_instant(
        self, read: Read, conversation: int
    ) -> None:
        comments = comments_of(read(AGENT_USERNAME, conversation))
        assert [c["created_at"] for c in comments] == [
            "2026-10-19T14:05:00Z",
            "2026-10-19T15:05:00Z",
            "2026-10-19T16:05:00Z",
            "2026-10-19T17:05:00Z",
        ]

    def test_both_profiles_see_the_same_comments(
        self, read: Read, conversation: int
    ) -> None:
        assert comments_of(read(REQUESTER_USERNAME, conversation)) == comments_of(
            read(AGENT_USERNAME, conversation)
        )

    def test_the_answer_to_a_comment_includes_the_earlier_ones(
        self, comment: PostComment, conversation: int
    ) -> None:
        answered = comment(AGENT_USERNAME, conversation, "Quinto")
        assert [c["body"] for c in comments_of(answered)][-2:] == ["Cuarto", "Quinto"]

    def test_orders_by_instant_even_if_stored_out_of_order(
        self, read: Read, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        for body, delay in (("Tarde", 2 * HOUR), ("Temprano", HOUR)):
            session.add(
                Comment(
                    ticket_id=ticket_id,
                    author_id=REQUESTER_ID,
                    body=body,
                    created_at=CREATED_AT + delay,
                )
            )
        session.commit()
        bodies = [c["body"] for c in comments_of(read(AGENT_USERNAME, ticket_id))]
        assert bodies == ["Temprano", "Tarde"]

    def test_orders_by_recording_when_the_instant_is_the_same(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        for body in ("Uno", "Dos", "Tres"):
            answered = comment(AGENT_USERNAME, ticket_id, body)
        assert [c["body"] for c in comments_of(answered)] == ["Uno", "Dos", "Tres"]

    def test_shows_only_the_comments_of_that_ticket(
        self, comment: PostComment, read: Read, session: Session
    ) -> None:
        other_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        comment(AGENT_USERNAME, other_id, "De otro ticket")
        assert comments_of(read(AGENT_USERNAME, ticket_id)) == []

    def test_a_ticket_without_comments_has_an_empty_list(
        self, read: Read, session: Session
    ) -> None:
        assert comments_of(read(AGENT_USERNAME, add_ticket_id(session))) == []

    def test_another_requester_does_not_see_the_comments(
        self, read: Read, conversation: int
    ) -> None:
        response = read(OTHER_REQUESTER_USERNAME, conversation)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)

    def test_the_comment_action_follows_the_status(
        self, read: Read, session: Session
    ) -> None:
        actions = {
            status: read(REQUESTER_USERNAME, add_ticket_in_id(session, status)).json()[
                "allowed_actions"
            ]
            for status in (*COMMENTABLE, *NOT_COMMENTABLE)
        }
        offering = {status for status, names in actions.items() if "comment" in names}
        assert offering == set(COMMENTABLE)


@pytest.fixture
def listing(client: TestClient, login_as: LoginAs) -> Listing:
    def fetch(username: str, view: str) -> Response:
        return client.get(
            TICKETS_URL, headers=login_as(username), params={"view": view}
        )

    return fetch


@pytest.mark.usefixtures("demo_data")
class TestCommentCount:
    @pytest.mark.parametrize(("username", "view"), LISTINGS)
    def test_each_listing_counts_the_comments_of_each_ticket(
        self, listing: Listing, session: Session, username: str, view: str
    ) -> None:
        quiet = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        single = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        several = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        add_comments(session, single, 1)
        add_comments(session, several, 3)
        assert counts_of(listing(username, view)) == {quiet: 0, single: 1, several: 3}

    def test_the_count_includes_every_author(
        self, comment: PostComment, listing: Listing, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        for username in (REQUESTER_USERNAME, AGENT_USERNAME, OTHER_AGENT_USERNAME):
            comment(username, ticket_id, BODY)
        assert counts_of(listing(REQUESTER_USERNAME, "mine")) == {ticket_id: 3}

    def test_a_finished_ticket_keeps_its_count(
        self, listing: Listing, session: Session
    ) -> None:
        closed = add_ticket_in_id(session, TicketStatus.CLOSED)
        add_comments(session, closed, 2)
        assert counts_of(listing(REQUESTER_USERNAME, "mine")) == {closed: 2}

    def test_the_comments_of_another_requester_are_not_counted(
        self, listing: Listing, session: Session
    ) -> None:
        mine = add_ticket_id(session)
        theirs = add_ticket_id(session, requester_id=OTHER_REQUESTER_ID)
        add_comments(session, theirs, 4)
        assert counts_of(listing(REQUESTER_USERNAME, "mine")) == {mine: 0}

    def test_the_detail_counts_the_comments_it_lists(
        self, read: Read, session: Session
    ) -> None:
        ticket_id = add_ticket_id(session)
        add_comments(session, ticket_id, 3)
        detail = read(REQUESTER_USERNAME, ticket_id).json()
        assert (detail["comment_count"], len(detail["comments"])) == (3, 3)

    def test_the_answer_to_a_comment_counts_the_new_one(
        self, comment: PostComment, session: Session
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        counts = [
            comment(AGENT_USERNAME, ticket_id, BODY).json()["comment_count"]
            for _ in range(3)
        ]
        assert counts == [1, 2, 3]

    def test_a_new_ticket_starts_without_comments(
        self, client: TestClient, login_as: LoginAs
    ) -> None:
        created = post_ticket(client, login_as(REQUESTER_USERNAME))
        assert created.json()["comment_count"] == 0


@pytest.mark.usefixtures("demo_data")
class TestCost:
    def queries_while(self, engine: Engine, call: Callable[[], Response]) -> list[str]:
        statements: list[str] = []

        def on_query(
            _connection: Any, _cursor: Any, statement: str, *_rest: Any
        ) -> None:
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", on_query)
        try:
            call()
        finally:
            event.remove(engine, "before_cursor_execute", on_query)
        return statements

    def test_reading_does_not_query_once_per_comment(
        self,
        engine: Engine,
        comment: PostComment,
        read: Read,
        session: Session,
    ) -> None:
        single_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        comment(REQUESTER_USERNAME, single_id, "Uno")
        full_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        for username in (REQUESTER_USERNAME, AGENT_USERNAME, OTHER_AGENT_USERNAME) * 3:
            comment(username, full_id, "Texto")
        single = self.queries_while(engine, lambda: read(AGENT_USERNAME, single_id))
        full = self.queries_while(engine, lambda: read(AGENT_USERNAME, full_id))
        assert len(full) == len(single)

    def test_the_authors_of_the_history_and_the_comments_are_read_together(
        self,
        engine: Engine,
        comment: PostComment,
        read: Read,
        session: Session,
    ) -> None:
        ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
        for username in (REQUESTER_USERNAME, AGENT_USERNAME, OTHER_AGENT_USERNAME):
            comment(username, ticket_id, "Texto")
        statements = self.queries_while(
            engine, lambda: read(REQUESTER_USERNAME, ticket_id)
        )
        assert len([s for s in statements if "users.id IN" in s]) == 1

    @pytest.mark.parametrize(("username", "view"), LISTINGS)
    def test_listing_does_not_query_once_per_ticket_or_comment(
        self,
        engine: Engine,
        listing: Listing,
        session: Session,
        username: str,
        view: str,
    ) -> None:
        add_comments(session, add_ticket_in_id(session, TicketStatus.IN_PROGRESS), 1)
        few = self.queries_while(engine, lambda: listing(username, view))
        for _ in range(5):
            ticket_id = add_ticket_in_id(session, TicketStatus.IN_PROGRESS)
            add_comments(session, ticket_id, 4)
        many = self.queries_while(engine, lambda: listing(username, view))
        assert len(many) == len(few)


class TestImmutability:
    def test_comments_only_accept_creation(self, app: FastAPI) -> None:
        operations = published_operations(app)
        methods = {
            method
            for path, path_methods in operations.items()
            if path.endswith("/comments")
            for method in path_methods
        }
        assert methods == {"post"}
