import pytest

from droidesk_api.core.errors import ActionNotAllowedError, ForbiddenError
from droidesk_api.identity.enums import Role
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.lifecycle import (
    TRANSITIONS,
    Relation,
    TicketAction,
    Viewer,
    allowed_actions,
    authorize_transition,
    comment_resumes_hold,
    relation_of,
)

OWNER = Viewer(Role.REQUESTER, Relation.OWNER)
FOREIGN_REQUESTER = Viewer(Role.REQUESTER, Relation.OTHER)
ASSIGNEE = Viewer(Role.AGENT, Relation.ASSIGNEE)
OTHER_AGENT = Viewer(Role.AGENT, Relation.OTHER)
ALL_VIEWERS = [OWNER, FOREIGN_REQUESTER, ASSIGNEE, OTHER_AGENT]

TRANSITION_ACTIONS = [
    TicketAction.TAKE,
    TicketAction.CANCEL,
    TicketAction.HOLD,
    TicketAction.RESUME,
    TicketAction.RESOLVE,
    TicketAction.CLOSE,
    TicketAction.REOPEN,
]

# Una fila por cada transición de la tabla de ADL-008: (acción, desde, hacia, quién).
ADL_008_ROWS = [
    (TicketAction.TAKE, TicketStatus.OPEN, TicketStatus.IN_PROGRESS, OTHER_AGENT),
    (TicketAction.CANCEL, TicketStatus.OPEN, TicketStatus.CANCELLED, OWNER),
    (TicketAction.HOLD, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD, ASSIGNEE),
    (TicketAction.RESUME, TicketStatus.ON_HOLD, TicketStatus.IN_PROGRESS, ASSIGNEE),
    (TicketAction.RESOLVE, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, ASSIGNEE),
    (TicketAction.CLOSE, TicketStatus.RESOLVED, TicketStatus.CLOSED, OWNER),
    (TicketAction.REOPEN, TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS, OWNER),
]
ACTOR_BY_ACTION = {action: actor for action, _, _, actor in ADL_008_ROWS}
SOURCE_BY_ACTION = {action: source for action, source, _, _ in ADL_008_ROWS}


def test_table_has_one_row_per_adl_transition() -> None:
    assert len(TRANSITIONS) == len(ADL_008_ROWS)


@pytest.mark.parametrize(("action", "source", "target", "actor"), ADL_008_ROWS)
def test_adl_row_leads_to_its_target(
    action: TicketAction, source: TicketStatus, target: TicketStatus, actor: Viewer
) -> None:
    assert authorize_transition(action, source, actor).target == target


@pytest.mark.parametrize(("action", "source", "target", "actor"), ADL_008_ROWS)
def test_adl_row_is_offered_to_its_actor(
    action: TicketAction, source: TicketStatus, target: TicketStatus, actor: Viewer
) -> None:
    assert action in allowed_actions(source, actor)


INVALID_STATE_PAIRS = [
    (action, status)
    for action in TRANSITION_ACTIONS
    for status in TicketStatus
    if status != SOURCE_BY_ACTION[action]
]


@pytest.mark.parametrize(("action", "status"), INVALID_STATE_PAIRS)
def test_action_is_rejected_outside_its_source_status(
    action: TicketAction, status: TicketStatus
) -> None:
    with pytest.raises(ActionNotAllowedError):
        authorize_transition(action, status, ACTOR_BY_ACTION[action])


@pytest.mark.parametrize(
    ("action", "viewer"),
    [
        (TicketAction.TAKE, OWNER),
        (TicketAction.HOLD, OWNER),
        (TicketAction.RESUME, OWNER),
        (TicketAction.RESOLVE, OWNER),
        (TicketAction.CANCEL, ASSIGNEE),
        (TicketAction.CLOSE, ASSIGNEE),
        (TicketAction.REOPEN, OTHER_AGENT),
    ],
)
def test_role_without_the_action_is_forbidden(
    action: TicketAction, viewer: Viewer
) -> None:
    with pytest.raises(ForbiddenError):
        authorize_transition(action, SOURCE_BY_ACTION[action], viewer)


@pytest.mark.parametrize(
    ("action", "viewer"),
    [
        (TicketAction.HOLD, OTHER_AGENT),
        (TicketAction.RESUME, OTHER_AGENT),
        (TicketAction.RESOLVE, OTHER_AGENT),
        (TicketAction.CANCEL, FOREIGN_REQUESTER),
        (TicketAction.CLOSE, FOREIGN_REQUESTER),
        (TicketAction.REOPEN, FOREIGN_REQUESTER),
    ],
)
def test_right_role_without_the_relation_is_not_allowed(
    action: TicketAction, viewer: Viewer
) -> None:
    with pytest.raises(ActionNotAllowedError):
        authorize_transition(action, SOURCE_BY_ACTION[action], viewer)


@pytest.mark.parametrize("action", [TicketAction.COMMENT, TicketAction.CHANGE_PRIORITY])
def test_non_transition_actions_are_not_authorized_as_transitions(
    action: TicketAction,
) -> None:
    with pytest.raises(ActionNotAllowedError):
        authorize_transition(action, TicketStatus.OPEN, ASSIGNEE)


def test_state_rejection_explains_action_and_status() -> None:
    with pytest.raises(ActionNotAllowedError) as raised:
        authorize_transition(TicketAction.CLOSE, TicketStatus.IN_PROGRESS, OWNER)
    assert (
        raised.value.message
        == "La acción «Confirmar cierre» no está disponible con el ticket en estado «En progreso»."
    )


def test_owner_relation_rejection_names_the_ticket_creator() -> None:
    with pytest.raises(ActionNotAllowedError) as raised:
        authorize_transition(
            TicketAction.CLOSE, TicketStatus.RESOLVED, FOREIGN_REQUESTER
        )
    assert (
        raised.value.message
        == "Solo quien creó el ticket puede realizar la acción «Confirmar cierre»."
    )


def test_relation_rejection_explains_who_can_do_it() -> None:
    with pytest.raises(ActionNotAllowedError) as raised:
        authorize_transition(TicketAction.HOLD, TicketStatus.IN_PROGRESS, OTHER_AGENT)
    assert (
        raised.value.message
        == "Solo el agente asignado al ticket puede realizar la acción «Dejar en espera»."
    )


def test_role_rejection_explains_the_action() -> None:
    with pytest.raises(ForbiddenError) as raised:
        authorize_transition(TicketAction.TAKE, TicketStatus.OPEN, OWNER)
    assert raised.value.message == "Tu perfil no puede realizar la acción «Tomar»."


ALLOWED_ACTIONS = [
    (TicketStatus.OPEN, OWNER, [TicketAction.CANCEL, TicketAction.COMMENT]),
    (
        TicketStatus.OPEN,
        OTHER_AGENT,
        [TicketAction.TAKE, TicketAction.COMMENT, TicketAction.CHANGE_PRIORITY],
    ),
    (TicketStatus.IN_PROGRESS, OWNER, [TicketAction.COMMENT]),
    (
        TicketStatus.IN_PROGRESS,
        ASSIGNEE,
        [
            TicketAction.HOLD,
            TicketAction.RESOLVE,
            TicketAction.COMMENT,
            TicketAction.CHANGE_PRIORITY,
        ],
    ),
    (
        TicketStatus.IN_PROGRESS,
        OTHER_AGENT,
        [TicketAction.COMMENT, TicketAction.CHANGE_PRIORITY],
    ),
    (TicketStatus.ON_HOLD, OWNER, [TicketAction.COMMENT]),
    (
        TicketStatus.ON_HOLD,
        ASSIGNEE,
        [TicketAction.RESUME, TicketAction.COMMENT, TicketAction.CHANGE_PRIORITY],
    ),
    (
        TicketStatus.ON_HOLD,
        OTHER_AGENT,
        [TicketAction.COMMENT, TicketAction.CHANGE_PRIORITY],
    ),
    (
        TicketStatus.RESOLVED,
        OWNER,
        [TicketAction.CLOSE, TicketAction.REOPEN, TicketAction.COMMENT],
    ),
    (TicketStatus.RESOLVED, ASSIGNEE, [TicketAction.COMMENT]),
    (TicketStatus.RESOLVED, OTHER_AGENT, [TicketAction.COMMENT]),
]


@pytest.mark.parametrize(("status", "viewer", "expected"), ALLOWED_ACTIONS)
def test_allowed_actions_follow_status_role_and_relation(
    status: TicketStatus, viewer: Viewer, expected: list[TicketAction]
) -> None:
    assert allowed_actions(status, viewer) == expected


@pytest.mark.parametrize(
    "status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD]
)
def test_foreign_requester_has_no_actions(status: TicketStatus) -> None:
    assert allowed_actions(status, FOREIGN_REQUESTER) == []


@pytest.mark.parametrize("status", [TicketStatus.CLOSED, TicketStatus.CANCELLED])
@pytest.mark.parametrize("viewer", ALL_VIEWERS)
def test_final_status_offers_no_actions(status: TicketStatus, viewer: Viewer) -> None:
    assert allowed_actions(status, viewer) == []


def test_requester_comment_resumes_a_ticket_on_hold() -> None:
    assert comment_resumes_hold(TicketStatus.ON_HOLD, OWNER) is True


def test_foreign_requester_comment_keeps_the_ticket_on_hold() -> None:
    assert comment_resumes_hold(TicketStatus.ON_HOLD, FOREIGN_REQUESTER) is False


@pytest.mark.parametrize("viewer", [ASSIGNEE, OTHER_AGENT])
def test_agent_comment_keeps_the_ticket_on_hold(viewer: Viewer) -> None:
    assert comment_resumes_hold(TicketStatus.ON_HOLD, viewer) is False


@pytest.mark.parametrize(
    "status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED]
)
def test_requester_comment_does_not_resume_outside_hold(status: TicketStatus) -> None:
    assert comment_resumes_hold(status, OWNER) is False


def test_requester_is_the_owner_of_their_ticket() -> None:
    assert relation_of(user_id=1, requester_id=1, assignee_id=None) == Relation.OWNER


def test_agent_is_the_assignee_of_their_ticket() -> None:
    assert relation_of(user_id=5, requester_id=1, assignee_id=5) == Relation.ASSIGNEE


def test_other_agent_has_no_relation_with_an_assigned_ticket() -> None:
    assert relation_of(user_id=6, requester_id=1, assignee_id=5) == Relation.OTHER


def test_agent_has_no_relation_with_an_unassigned_ticket() -> None:
    assert relation_of(user_id=5, requester_id=1, assignee_id=None) == Relation.OTHER
