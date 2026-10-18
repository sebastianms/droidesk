from dataclasses import dataclass
from enum import StrEnum

from droidesk_api.core.errors import ActionNotAllowedError, ForbiddenError
from droidesk_api.identity.enums import Role
from droidesk_api.tickets.enums import TicketStatus

FINAL_STATUSES = frozenset({TicketStatus.CLOSED, TicketStatus.CANCELLED})
PRIORITY_EDITABLE_STATUSES = frozenset(
    {TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.ON_HOLD}
)


class TicketAction(StrEnum):
    TAKE = "take"
    CANCEL = "cancel"
    HOLD = "hold"
    RESUME = "resume"
    RESOLVE = "resolve"
    CLOSE = "close"
    REOPEN = "reopen"
    COMMENT = "comment"
    CHANGE_PRIORITY = "change_priority"


class Relation(StrEnum):
    OWNER = "owner"
    ASSIGNEE = "assignee"
    OTHER = "other"


@dataclass(frozen=True)
class Viewer:
    """Quién consulta o actúa, con su rol y su relación con el ticket."""

    role: Role
    relation: Relation


@dataclass(frozen=True)
class Transition:
    action: TicketAction
    source: TicketStatus
    target: TicketStatus
    role: Role
    relation: Relation | None = None  # None: cualquier usuario con ese rol


TRANSITIONS = (
    Transition(
        TicketAction.TAKE, TicketStatus.OPEN, TicketStatus.IN_PROGRESS, Role.AGENT
    ),
    Transition(
        TicketAction.CANCEL,
        TicketStatus.OPEN,
        TicketStatus.CANCELLED,
        Role.REQUESTER,
        Relation.OWNER,
    ),
    Transition(
        TicketAction.HOLD,
        TicketStatus.IN_PROGRESS,
        TicketStatus.ON_HOLD,
        Role.AGENT,
        Relation.ASSIGNEE,
    ),
    Transition(
        TicketAction.RESUME,
        TicketStatus.ON_HOLD,
        TicketStatus.IN_PROGRESS,
        Role.AGENT,
        Relation.ASSIGNEE,
    ),
    Transition(
        TicketAction.RESOLVE,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        Role.AGENT,
        Relation.ASSIGNEE,
    ),
    Transition(
        TicketAction.CLOSE,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
        Role.REQUESTER,
        Relation.OWNER,
    ),
    Transition(
        TicketAction.REOPEN,
        TicketStatus.RESOLVED,
        TicketStatus.IN_PROGRESS,
        Role.REQUESTER,
        Relation.OWNER,
    ),
)

ACTION_LABELS = {
    TicketAction.TAKE: "Tomar",
    TicketAction.CANCEL: "Cancelar",
    TicketAction.HOLD: "Dejar en espera",
    TicketAction.RESUME: "Retomar",
    TicketAction.RESOLVE: "Resolver",
    TicketAction.CLOSE: "Confirmar cierre",
    TicketAction.REOPEN: "Reabrir",
    TicketAction.COMMENT: "Comentar",
    TicketAction.CHANGE_PRIORITY: "Cambiar prioridad",
}
STATUS_LABELS = {
    TicketStatus.OPEN: "Abierto",
    TicketStatus.IN_PROGRESS: "En progreso",
    TicketStatus.ON_HOLD: "En espera",
    TicketStatus.RESOLVED: "Resuelto",
    TicketStatus.CLOSED: "Cerrado",
    TicketStatus.CANCELLED: "Cancelado",
}
RELATION_REQUIREMENTS = {
    Relation.OWNER: "Solo quien creó el ticket puede realizar la acción «{action}».",
    Relation.ASSIGNEE: "Solo el agente asignado al ticket puede realizar la acción «{action}».",
}


def relation_of(user_id: int, requester_id: int, assignee_id: int | None) -> Relation:
    if user_id == requester_id:
        return Relation.OWNER
    if user_id == assignee_id:
        return Relation.ASSIGNEE
    return Relation.OTHER


def authorize_transition(
    action: TicketAction, status: TicketStatus, viewer: Viewer
) -> Transition:
    label = ACTION_LABELS[action]
    candidates = [t for t in TRANSITIONS if t.action == action]
    if not candidates:
        raise ActionNotAllowedError(f"La acción «{label}» no es un cambio de estado.")
    if not any(t.role == viewer.role for t in candidates):
        raise ForbiddenError(f"Tu perfil no puede realizar la acción «{label}».")
    transition = next((t for t in candidates if t.source == status), None)
    if transition is None:
        raise ActionNotAllowedError(
            f"La acción «{label}» no está disponible con el ticket en estado «{STATUS_LABELS[status]}»."
        )
    missing = _missing_relation(transition, viewer)
    if missing is not None:
        raise ActionNotAllowedError(RELATION_REQUIREMENTS[missing].format(action=label))
    return transition


def allowed_actions(status: TicketStatus, viewer: Viewer) -> list[TicketAction]:
    return [action for action in TicketAction if _is_allowed(action, status, viewer)]


def comment_resumes_hold(status: TicketStatus, viewer: Viewer) -> bool:
    return (
        status == TicketStatus.ON_HOLD
        and viewer.role == Role.REQUESTER
        and viewer.relation == Relation.OWNER
    )


def _is_allowed(action: TicketAction, status: TicketStatus, viewer: Viewer) -> bool:
    if action == TicketAction.COMMENT:
        return _can_comment(status, viewer)
    if action == TicketAction.CHANGE_PRIORITY:
        return viewer.role == Role.AGENT and status in PRIORITY_EDITABLE_STATUSES
    return any(
        t.action == action
        and t.source == status
        and t.role == viewer.role
        and _missing_relation(t, viewer) is None
        for t in TRANSITIONS
    )


def _can_comment(status: TicketStatus, viewer: Viewer) -> bool:
    if status in FINAL_STATUSES:
        return False
    return viewer.role == Role.AGENT or viewer.relation == Relation.OWNER


def _missing_relation(transition: Transition, viewer: Viewer) -> Relation | None:
    required = transition.relation
    return required if required is not None and required != viewer.relation else None
