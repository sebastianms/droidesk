from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from sqlalchemy.orm import Mapped, aliased
from sqlmodel import Session, col, select, update
from sqlmodel.sql.expression import Select

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import NewEvent, list_events, record_event
from droidesk_api.core.clock import Clock
from droidesk_api.core.db import ColumnValues, persisted_id
from droidesk_api.core.errors import (
    ActionNotAllowedError,
    AlreadyTakenError,
    DomainError,
    ForbiddenError,
    InvalidFieldError,
    NotFoundError,
)
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.identity.service import users_by_id
from droidesk_api.sla.calendar import BusinessCalendar
from droidesk_api.tickets import presenter, schemas
from droidesk_api.tickets.access import TICKET_NOT_FOUND_MESSAGE, ensure_can_view
from droidesk_api.tickets.enums import TicketStatus
from droidesk_api.tickets.lifecycle import (
    ACTION_LABELS,
    FINAL_STATUSES,
    TicketAction,
    Transition,
    Viewer,
    allowed_actions,
    authorize_transition,
    relation_of,
)
from droidesk_api.tickets.models import Category, Ticket
from droidesk_api.tickets.presenter import DetailFacts, TicketRow
from droidesk_api.tickets.ticket_sla import TicketSla

RowStatement = Select[Ticket, Category, User, User | None]
Requester = aliased(User)
Assignee = aliased(User)

DEFAULT_VIEWS = {
    Role.REQUESTER: schemas.TicketView.MINE,
    Role.AGENT: schemas.TicketView.QUEUE,
}
DateColumn = Mapped[datetime | None]
# Fecha que cada acción de estado fija con la hora actual en el ticket, o vacía (reabrir quita la resolución).
STAMPED_DATES: dict[TicketAction, DateColumn] = {
    TicketAction.CANCEL: col(Ticket.cancelled_at),
    TicketAction.HOLD: col(Ticket.on_hold_since),
    TicketAction.RESOLVE: col(Ticket.resolved_at),
    TicketAction.CLOSE: col(Ticket.closed_at),
}
CLEARED_DATES: dict[TicketAction, DateColumn] = {
    TicketAction.REOPEN: col(Ticket.resolved_at)
}


@dataclass(frozen=True)
class Change:
    """Una transición autorizada, con quién la aplica y cuándo."""

    transition: Transition
    actor: User
    now: datetime


class TicketService:
    """Casos de uso de los tickets; cada uno que escribe lo hace en una sola transacción."""

    def __init__(
        self, session: Session, clock: Clock, calendar: BusinessCalendar
    ) -> None:
        self._session = session
        self._clock = clock
        self._sla = TicketSla(session, calendar)

    def create_ticket(
        self, requester: User, data: schemas.TicketCreate
    ) -> schemas.TicketDetail:
        if self._session.get(Category, data.category_id) is None:
            raise InvalidFieldError("category_id", "La categoría no existe.")
        now = self._clock.now()
        ticket = self._new_ticket(requester, data, now)
        self._session.add(ticket)
        self._session.flush()
        ticket_id = persisted_id(ticket)
        record_event(
            self._session,
            NewEvent(
                ticket_id=ticket_id,
                actor_id=persisted_id(requester),
                kind=EventKind.CREATED,
                created_at=now,
                to_value=TicketStatus.OPEN.value,
            ),
        )
        self._session.commit()
        return self.get_ticket_for(requester, ticket_id)

    def list_tickets(
        self, user: User, view: schemas.TicketView | None
    ) -> list[schemas.TicketSummary]:
        listing = self._LISTINGS.get((user.role, view or DEFAULT_VIEWS[user.role]))
        if listing is None:
            raise ForbiddenError("Tu perfil no puede ver esta lista.")
        return listing(self, user)

    def _list_my_tickets(self, requester: User) -> list[schemas.TicketSummary]:
        statement = (
            _row_statement()
            .where(col(Ticket.requester_id) == persisted_id(requester))
            .order_by(col(Ticket.created_at).desc(), col(Ticket.id).desc())
        )
        return self._summaries(self._rows(statement))

    def _list_queue(self, _agent: User) -> list[schemas.TicketSummary]:
        return self._queue_summaries(_unfinished_statement())

    def _list_assigned(self, agent: User) -> list[schemas.TicketSummary]:
        statement = _unfinished_statement().where(
            col(Ticket.assignee_id) == persisted_id(agent)
        )
        return self._queue_summaries(statement)

    _LISTINGS: ClassVar[
        dict[
            tuple[Role, schemas.TicketView],
            Callable[[TicketService, User], list[schemas.TicketSummary]],
        ]
    ] = {
        (Role.REQUESTER, schemas.TicketView.MINE): _list_my_tickets,
        (Role.AGENT, schemas.TicketView.QUEUE): _list_queue,
        (Role.AGENT, schemas.TicketView.ASSIGNED): _list_assigned,
    }

    def get_ticket_for(self, user: User, ticket_id: int) -> schemas.TicketDetail:
        row = self._visible_row(user, ticket_id)
        facts = DetailFacts(
            sla=self._sla.view_of(row.ticket, self._clock.now()),
            allowed_actions=allowed_actions(
                row.ticket.status, _viewer_of(user, row.ticket)
            ),
            history=self._history_of(row.ticket),
        )
        return presenter.to_detail(row, facts)

    def apply_transition(
        self, user: User, ticket_id: int, action: TicketAction
    ) -> schemas.TicketDetail:
        ticket = self._visible_row(user, ticket_id).ticket
        change = Change(_authorize(user, ticket, action), user, self._clock.now())
        self._move(ticket, change)
        for event in _transition_events(ticket_id, change):
            record_event(self._session, event)
        self._session.commit()
        return self.get_ticket_for(user, ticket_id)

    def _history_of(self, ticket: Ticket) -> list[schemas.Event]:
        """Las entradas en orden cronológico; los autores se leen en una sola consulta."""
        events = list_events(self._session, persisted_id(ticket))
        actors = users_by_id(self._session, {event.actor_id for event in events})
        return [presenter.to_event(event, actors[event.actor_id]) for event in events]

    def _new_ticket(
        self, requester: User, data: schemas.TicketCreate, now: datetime
    ) -> Ticket:
        return Ticket(
            title=data.title,
            description=data.description,
            priority=data.priority,
            category_id=data.category_id,
            requester_id=persisted_id(requester),
            created_at=now,
            updated_at=now,
            sla_due_at=self._sla.initial_due_at(data.priority, now),
        )

    def _move(self, ticket: Ticket, change: Change) -> None:
        """Actualización condicional: si otro cambió el estado antes, no afecta filas y se rechaza."""
        transition = change.transition
        statement = (
            update(Ticket)
            .where(
                col(Ticket.id) == persisted_id(ticket),
                col(Ticket.status) == transition.source,
            )
            .values(status=transition.target, updated_at=change.now)
            .values(self._effects_of(ticket, change))
        )
        if self._session.exec(statement).rowcount == 0:
            raise self._lost_race(persisted_id(ticket), transition, change.actor)

    def _effects_of(self, ticket: Ticket, change: Change) -> ColumnValues:
        action = change.transition.action
        if action == TicketAction.TAKE:
            return {col(Ticket.assignee_id): persisted_id(change.actor)}
        if action == TicketAction.RESUME:
            return self._sla.resume_values(ticket, change.now)
        return _date_effects(action, change.now)

    def _lost_race(
        self, ticket_id: int, transition: Transition, actor: User
    ) -> DomainError:
        """Quien pierde una toma ante otro agente recibe `already_taken`; en las demás acciones, solo que el estado cambió."""
        if transition.action == TicketAction.TAKE:
            assignee_id = self._session.exec(
                select(col(Ticket.assignee_id)).where(col(Ticket.id) == ticket_id)
            ).one()
            if _taken_by_another(assignee_id, actor):
                return AlreadyTakenError()
        label = ACTION_LABELS[transition.action]
        return ActionNotAllowedError(
            f"La acción «{label}» ya no está disponible: el ticket cambió de estado."
        )

    def _visible_row(self, user: User, ticket_id: int) -> TicketRow:
        rows = self._rows(_row_statement().where(col(Ticket.id) == ticket_id))
        if not rows:
            raise NotFoundError(TICKET_NOT_FOUND_MESSAGE)
        ensure_can_view(user, rows[0].ticket)
        return rows[0]

    def _rows(self, statement: RowStatement) -> list[TicketRow]:
        return [TicketRow(*columns) for columns in self._session.exec(statement)]

    def _queue_summaries(self, statement: RowStatement) -> list[schemas.TicketSummary]:
        rows = sorted(
            self._rows(statement), key=lambda row: self._sla.queue_key(row.ticket)
        )
        return self._summaries(rows)

    def _summaries(self, rows: Sequence[TicketRow]) -> list[schemas.TicketSummary]:
        now = self._clock.now()
        return [
            presenter.to_summary(row, self._sla.view_of(row.ticket, now))
            for row in rows
        ]


def _row_statement() -> RowStatement:
    return (
        select(Ticket, Category, Requester, Assignee)
        .join(Category, col(Category.id) == col(Ticket.category_id))
        .join(Requester, col(Ticket.requester_id) == Requester.id)
        .outerjoin(Assignee, col(Ticket.assignee_id) == Assignee.id)
    )


def _unfinished_statement() -> RowStatement:
    return _row_statement().where(col(Ticket.status).not_in(tuple(FINAL_STATUSES)))


def _viewer_of(user: User, ticket: Ticket) -> Viewer:
    relation = relation_of(persisted_id(user), ticket.requester_id, ticket.assignee_id)
    return Viewer(user.role, relation)


def _authorize(user: User, ticket: Ticket, action: TicketAction) -> Transition:
    """Si el ticket ya tiene otro dueño, tomarlo es `already_taken` aunque la lista del agente estuviera desactualizada."""
    try:
        return authorize_transition(action, ticket.status, _viewer_of(user, ticket))
    except ActionNotAllowedError:
        if action == TicketAction.TAKE and _taken_by_another(ticket.assignee_id, user):
            raise AlreadyTakenError from None
        raise


def _taken_by_another(assignee_id: int | None, agent: User) -> bool:
    return assignee_id not in (None, persisted_id(agent))


def _date_effects(
    action: TicketAction, now: datetime
) -> dict[DateColumn, datetime | None]:
    if action in CLEARED_DATES:
        return {CLEARED_DATES[action]: None}
    return {STAMPED_DATES[action]: now}


def _transition_events(ticket_id: int, change: Change) -> list[NewEvent]:
    """Tomar un ticket lo asigna y además cambia su estado: dos eventos, en ese orden."""
    transition, actor = change.transition, change.actor
    events = []
    if transition.action == TicketAction.TAKE:
        events.append(
            NewEvent(
                ticket_id=ticket_id,
                actor_id=persisted_id(actor),
                kind=EventKind.ASSIGNED,
                created_at=change.now,
                to_value=actor.name,
            )
        )
    events.append(
        NewEvent(
            ticket_id=ticket_id,
            actor_id=persisted_id(actor),
            kind=EventKind.STATUS_CHANGED,
            created_at=change.now,
            from_value=transition.source.value,
            to_value=transition.target.value,
        )
    )
    return events
