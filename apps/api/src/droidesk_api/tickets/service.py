from collections.abc import Callable, Sequence
from datetime import datetime
from functools import cached_property
from typing import ClassVar

from sqlalchemy.orm import Mapped, aliased
from sqlmodel import Session, col, select, update
from sqlmodel.sql.expression import Select

from droidesk_api.audit.enums import EventKind
from droidesk_api.audit.recorder import NewEvent, record_event
from droidesk_api.core.clock import Clock
from droidesk_api.core.db import persisted_id
from droidesk_api.core.errors import (
    ActionNotAllowedError,
    ForbiddenError,
    InvalidFieldError,
    NotFoundError,
)
from droidesk_api.identity.enums import Role
from droidesk_api.identity.models import User
from droidesk_api.sla.calendar import BusinessCalendar, add_business_minutes
from droidesk_api.sla.models import SlaPolicy
from droidesk_api.sla.status import (
    SlaFacts,
    SlaState,
    sla_state,
    target_minutes,
)
from droidesk_api.tickets import presenter, schemas
from droidesk_api.tickets.access import TICKET_NOT_FOUND_MESSAGE, ensure_can_view
from droidesk_api.tickets.enums import Priority, TicketStatus
from droidesk_api.tickets.lifecycle import (
    ACTION_LABELS,
    TicketAction,
    Transition,
    Viewer,
    allowed_actions,
    authorize_transition,
    relation_of,
)
from droidesk_api.tickets.models import Category, Ticket
from droidesk_api.tickets.presenter import TicketRow

RowStatement = Select[Ticket, Category, User, User | None]
DateColumn = Mapped[datetime | None]
Requester = aliased(User)
Assignee = aliased(User)

DEFAULT_VIEWS = {
    Role.REQUESTER: schemas.TicketView.MINE,
    Role.AGENT: schemas.TicketView.QUEUE,
}
# Fecha que cada acción de estado fija con la hora actual en el ticket, o vacía (reabrir quita la resolución).
STAMPED_DATES = {
    TicketAction.CANCEL: col(Ticket.cancelled_at),
    TicketAction.HOLD: col(Ticket.on_hold_since),
    TicketAction.RESOLVE: col(Ticket.resolved_at),
    TicketAction.CLOSE: col(Ticket.closed_at),
}
CLEARED_DATES = {TicketAction.REOPEN: col(Ticket.resolved_at)}


class TicketService:
    """Casos de uso de los tickets; cada uno que escribe lo hace en una sola transacción."""

    def __init__(
        self, session: Session, clock: Clock, calendar: BusinessCalendar
    ) -> None:
        self._session = session
        self._clock = clock
        self._calendar = calendar

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

    # La US2 agrega aquí las vistas del agente: (AGENT, QUEUE) y (AGENT, ASSIGNED).
    _LISTINGS: ClassVar[
        dict[
            tuple[Role, schemas.TicketView],
            Callable[[TicketService, User], list[schemas.TicketSummary]],
        ]
    ] = {(Role.REQUESTER, schemas.TicketView.MINE): _list_my_tickets}

    def get_ticket_for(self, user: User, ticket_id: int) -> schemas.TicketDetail:
        row = self._visible_row(user, ticket_id)
        sla = self._sla_of(row.ticket, self._clock.now())
        actions = allowed_actions(row.ticket.status, _viewer_of(user, row.ticket))
        return presenter.to_detail(row, sla, actions)

    def apply_transition(
        self, user: User, ticket_id: int, action: TicketAction
    ) -> schemas.TicketDetail:
        ticket = self._visible_row(user, ticket_id).ticket
        transition = authorize_transition(
            action, ticket.status, _viewer_of(user, ticket)
        )
        now = self._clock.now()
        self._move(ticket_id, transition, _date_effects(action, now), now)
        record_event(
            self._session,
            NewEvent(
                ticket_id=ticket_id,
                actor_id=persisted_id(user),
                kind=EventKind.STATUS_CHANGED,
                created_at=now,
                from_value=transition.source.value,
                to_value=transition.target.value,
            ),
        )
        self._session.commit()
        return self.get_ticket_for(user, ticket_id)

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
            sla_due_at=add_business_minutes(
                now, self._target_minutes[data.priority], self._calendar
            ),
        )

    def _move(
        self,
        ticket_id: int,
        transition: Transition,
        effects: dict[DateColumn, datetime | None],
        now: datetime,
    ) -> None:
        """Actualización condicional: si otro cambió el estado antes, no afecta filas y se rechaza."""
        statement = (
            update(Ticket)
            .where(col(Ticket.id) == ticket_id, col(Ticket.status) == transition.source)
            .values(status=transition.target, updated_at=now)
            .values(effects)
        )
        if self._session.exec(statement).rowcount == 0:
            label = ACTION_LABELS[transition.action]
            raise ActionNotAllowedError(
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

    def _summaries(self, rows: Sequence[TicketRow]) -> list[schemas.TicketSummary]:
        now = self._clock.now()
        return [
            presenter.to_summary(row, self._sla_of(row.ticket, now)) for row in rows
        ]

    def _sla_of(self, ticket: Ticket, now: datetime) -> schemas.Sla:
        state = sla_state(self._facts(ticket), now, self._calendar)
        has_clock = state not in (None, SlaState.PAUSED)
        return schemas.Sla(state=state, due_at=ticket.sla_due_at if has_clock else None)

    def _facts(self, ticket: Ticket) -> SlaFacts:
        return SlaFacts(
            status=ticket.status,
            created_at=ticket.created_at,
            due_at=ticket.sla_due_at,
            target_minutes=self._target_minutes[ticket.priority],
            paused_minutes=ticket.sla_paused_minutes,
            on_hold_since=ticket.on_hold_since,
            resolved_at=ticket.resolved_at,
        )

    @cached_property
    def _target_minutes(self) -> dict[Priority, int]:
        policies = self._session.exec(select(SlaPolicy))
        return {
            policy.priority: target_minutes(
                policy.target_amount, policy.target_unit, self._calendar
            )
            for policy in policies
        }


def _row_statement() -> RowStatement:
    return (
        select(Ticket, Category, Requester, Assignee)
        .join(Category, col(Category.id) == col(Ticket.category_id))
        .join(Requester, col(Ticket.requester_id) == Requester.id)
        .outerjoin(Assignee, col(Ticket.assignee_id) == Assignee.id)
    )


def _viewer_of(user: User, ticket: Ticket) -> Viewer:
    relation = relation_of(persisted_id(user), ticket.requester_id, ticket.assignee_id)
    return Viewer(user.role, relation)


def _date_effects(
    action: TicketAction, now: datetime
) -> dict[DateColumn, datetime | None]:
    if action in STAMPED_DATES:
        return {STAMPED_DATES[action]: now}
    if action in CLEARED_DATES:
        return {CLEARED_DATES[action]: None}
    # `take` y `resume` suman asignación y recálculo del SLA: llegan con la cola (US2).
    raise ActionNotAllowedError(
        f"La acción «{ACTION_LABELS[action]}» aún no está disponible."
    )
