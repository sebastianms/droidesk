from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from droidesk_api.sla.calendar import (
    BusinessCalendar,
    add_business_minutes,
    business_minutes_between,
)
from droidesk_api.sla.enums import TargetUnit
from droidesk_api.tickets.enums import TicketStatus

MINUTES_PER_HOUR = 60
AT_RISK_DENOMINATOR = 4  # "Por vencer": queda menos de 1/4 (25 %) del plazo


class SlaState(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    PAUSED = "paused"
    MET = "met"
    MISSED = "missed"


@dataclass(frozen=True)
class SlaFacts:
    """Lo que el dominio necesita saber de un ticket para calcular su SLA."""

    status: TicketStatus
    created_at: datetime
    due_at: datetime
    target_minutes: int
    paused_minutes: int
    on_hold_since: datetime | None
    resolved_at: datetime | None


def target_minutes(amount: int, unit: TargetUnit, calendar: BusinessCalendar) -> int:
    minutes_per_unit = (
        MINUTES_PER_HOUR if unit == TargetUnit.HOURS else calendar.minutes_per_day
    )
    return amount * minutes_per_unit


def recalculated_due_at(facts: SlaFacts, calendar: BusinessCalendar) -> datetime:
    budget = facts.target_minutes + facts.paused_minutes
    return add_business_minutes(facts.created_at, budget, calendar)


def hold_pause_minutes(
    facts: SlaFacts, now: datetime, calendar: BusinessCalendar
) -> int:
    """Minutos hábiles que una espera suma al plazo: ninguno si empezó con el ticket ya vencido."""
    if facts.on_hold_since is None:
        raise ValueError("El ticket no está en espera.")
    if facts.on_hold_since >= facts.due_at:
        return 0
    return business_minutes_between(facts.on_hold_since, now, calendar)


def sla_state(
    facts: SlaFacts, now: datetime, calendar: BusinessCalendar
) -> SlaState | None:
    if facts.status == TicketStatus.CANCELLED:
        return None
    if facts.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        return _outcome(facts)
    if _is_paused(facts):
        return SlaState.PAUSED
    if now >= facts.due_at:
        return SlaState.BREACHED
    remaining = business_minutes_between(now, facts.due_at, calendar)
    return (
        SlaState.AT_RISK
        if remaining * AT_RISK_DENOMINATOR < facts.target_minutes
        else SlaState.ON_TRACK
    )


def queue_sort_key(facts: SlaFacts) -> tuple[bool, datetime, datetime]:
    """Primero el reloj corriendo y luego las esperas; en cada grupo, por vencimiento y antigüedad."""
    return facts.status == TicketStatus.ON_HOLD, facts.due_at, facts.created_at


def _outcome(facts: SlaFacts) -> SlaState:
    if facts.resolved_at is None:
        raise ValueError("Un ticket resuelto o cerrado debe tener fecha de resolución.")
    return SlaState.MET if facts.resolved_at <= facts.due_at else SlaState.MISSED


def _is_paused(facts: SlaFacts) -> bool:
    return (
        facts.status == TicketStatus.ON_HOLD
        and facts.on_hold_since is not None
        and facts.on_hold_since < facts.due_at
    )
