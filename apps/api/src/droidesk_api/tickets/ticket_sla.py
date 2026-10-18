from dataclasses import replace
from datetime import datetime
from functools import cached_property

from sqlmodel import Session, col, select

from droidesk_api.core.db import ColumnValues, persisted_id
from droidesk_api.sla.calendar import BusinessCalendar, add_business_minutes
from droidesk_api.sla.models import SlaPolicy
from droidesk_api.sla.status import (
    SlaFacts,
    SlaState,
    hold_pause_minutes,
    queue_sort_key,
    recalculated_due_at,
    sla_state,
    target_minutes,
)
from droidesk_api.tickets import schemas
from droidesk_api.tickets.enums import Priority
from droidesk_api.tickets.models import Ticket


class TicketSla:
    """El SLA de los tickets guardados: lo que se muestra al leer y lo que se recalcula al retomar."""

    def __init__(self, session: Session, calendar: BusinessCalendar) -> None:
        self._session = session
        self._calendar = calendar

    def initial_due_at(self, priority: Priority, created_at: datetime) -> datetime:
        budget = self._target_minutes[priority]
        return add_business_minutes(created_at, budget, self._calendar)

    def view_of(self, ticket: Ticket, now: datetime) -> schemas.Sla:
        state = sla_state(self._facts(ticket), now, self._calendar)
        has_clock = state not in (None, SlaState.PAUSED)
        return schemas.Sla(state=state, due_at=ticket.sla_due_at if has_clock else None)

    def queue_key(self, ticket: Ticket) -> tuple[bool, datetime, datetime, int]:
        """Orden de la cola; el id desempata para que el resultado sea estable."""
        return (*queue_sort_key(self._facts(ticket)), persisted_id(ticket))

    def resume_values(self, ticket: Ticket, now: datetime) -> ColumnValues:
        """La espera que termina suma al plazo sus minutos hábiles (ninguno si empezó vencido)."""
        facts = self._facts(ticket)
        paused_minutes = facts.paused_minutes + hold_pause_minutes(
            facts, now, self._calendar
        )
        due_at = recalculated_due_at(
            replace(facts, paused_minutes=paused_minutes), self._calendar
        )
        return {
            col(Ticket.sla_paused_minutes): paused_minutes,
            col(Ticket.sla_due_at): due_at,
            col(Ticket.on_hold_since): None,
        }

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
