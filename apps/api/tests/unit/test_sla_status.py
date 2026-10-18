from dataclasses import replace
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from droidesk_api.sla.calendar import BusinessCalendar, BusinessHours
from droidesk_api.sla.enums import TargetUnit
from droidesk_api.sla.status import (
    SlaFacts,
    SlaState,
    hold_pause_minutes,
    queue_sort_key,
    recalculated_due_at,
    sla_state,
    target_minutes,
)
from droidesk_api.tickets.enums import TicketStatus

SANTIAGO = ZoneInfo("America/Santiago")
CALENDAR = BusinessCalendar(
    zone=SANTIAGO, hours=BusinessHours(opens=time(9, 0), closes=time(18, 0))
)
HOUR = 60
DAY = 9 * HOUR


def local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SANTIAGO).astimezone(UTC)


CREATED = local(2026, 10, 19, 10)  # lunes
DUE = local(2026, 10, 20, 10)  # martes: una Alta de 1 día hábil


def facts(**changes: Any) -> SlaFacts:
    in_progress_alta = SlaFacts(
        status=TicketStatus.IN_PROGRESS,
        created_at=CREATED,
        due_at=DUE,
        target_minutes=DAY,
        paused_minutes=0,
        on_hold_since=None,
        resolved_at=None,
    )
    return replace(in_progress_alta, **changes)


class TestTargetMinutes:
    def test_hours_are_plain_hours(self) -> None:
        assert target_minutes(4, TargetUnit.HOURS, CALENDAR) == 4 * HOUR

    @pytest.mark.parametrize(
        ("days", "expected"), [(1, DAY), (3, 3 * DAY), (5, 5 * DAY)]
    )
    def test_days_are_whole_workdays(self, days: int, expected: int) -> None:
        assert target_minutes(days, TargetUnit.DAYS, CALENDAR) == expected

    def test_a_day_follows_the_length_of_the_workday(self) -> None:
        eight_hour_day = BusinessCalendar(
            zone=SANTIAGO, hours=BusinessHours(opens=time(9, 0), closes=time(17, 0))
        )
        assert target_minutes(1, TargetUnit.DAYS, eight_hour_day) == 8 * HOUR


class TestRecalculatedDueAt:
    def test_without_pauses_the_budget_is_the_target(self) -> None:
        assert recalculated_due_at(facts(), CALENDAR) == DUE

    def test_pauses_extend_the_deadline(self) -> None:
        assert recalculated_due_at(facts(paused_minutes=4 * HOUR), CALENDAR) == local(
            2026, 10, 20, 14
        )

    def test_a_new_target_counts_from_the_creation(self) -> None:
        critical = facts(target_minutes=4 * HOUR)
        assert recalculated_due_at(critical, CALENDAR) == local(2026, 10, 19, 14)

    def test_a_lower_priority_target_counts_from_the_creation_too(self) -> None:
        low = facts(target_minutes=5 * DAY)
        assert recalculated_due_at(low, CALENDAR) == local(2026, 10, 26, 10)


class TestHoldPauseMinutes:
    def test_hold_inside_the_deadline_pauses_its_whole_length(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 19, 11)
        )
        assert (
            hold_pause_minutes(on_hold, local(2026, 10, 19, 15), CALENDAR) == 4 * HOUR
        )

    def test_hold_that_crosses_the_deadline_still_pauses_its_whole_length(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 19, 17)
        )
        assert (
            hold_pause_minutes(on_hold, local(2026, 10, 20, 11), CALENDAR) == 3 * HOUR
        )

    def test_hold_that_starts_at_the_deadline_pauses_nothing(self) -> None:
        on_hold = facts(status=TicketStatus.ON_HOLD, on_hold_since=DUE)
        assert hold_pause_minutes(on_hold, local(2026, 10, 20, 15), CALENDAR) == 0

    def test_hold_that_starts_after_the_deadline_pauses_nothing(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 20, 12)
        )
        assert hold_pause_minutes(on_hold, local(2026, 10, 21, 12), CALENDAR) == 0

    def test_hold_counts_only_business_time(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 19, 17)
        )
        assert (
            hold_pause_minutes(on_hold, local(2026, 10, 20, 9, 30), CALENDAR)
            == HOUR + 30
        )

    def test_requires_a_hold_in_progress(self) -> None:
        with pytest.raises(ValueError, match="espera"):
            hold_pause_minutes(facts(), local(2026, 10, 19, 15), CALENDAR)


class TestSlaState:
    def test_a_cancelled_ticket_has_no_sla(self) -> None:
        assert (
            sla_state(facts(status=TicketStatus.CANCELLED), CREATED, CALENDAR) is None
        )

    @pytest.mark.parametrize("status", [TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
    def test_a_fresh_ticket_is_on_track(self, status: TicketStatus) -> None:
        assert sla_state(facts(status=status), CREATED, CALENDAR) == SlaState.ON_TRACK

    def test_at_the_threshold_the_ticket_is_still_on_track(self) -> None:
        assert (
            sla_state(facts(), local(2026, 10, 19, 16, 45), CALENDAR)
            == SlaState.ON_TRACK
        )

    def test_one_minute_below_the_threshold_the_ticket_is_at_risk(self) -> None:
        assert (
            sla_state(facts(), local(2026, 10, 19, 16, 46), CALENDAR)
            == SlaState.AT_RISK
        )

    def test_risk_counts_business_minutes_across_the_weekend(self) -> None:
        due_monday = facts(due_at=local(2026, 10, 26, 10))
        assert (
            sla_state(due_monday, local(2026, 10, 23, 17), CALENDAR) == SlaState.AT_RISK
        )

    def test_risk_threshold_uses_the_target_without_pauses(self) -> None:
        paused = facts(paused_minutes=4 * HOUR, due_at=local(2026, 10, 20, 14))
        assert (
            sla_state(paused, local(2026, 10, 20, 11, 30), CALENDAR)
            == SlaState.ON_TRACK
        )

    def test_at_the_deadline_the_ticket_is_breached(self) -> None:
        assert sla_state(facts(), DUE, CALENDAR) == SlaState.BREACHED

    def test_after_the_deadline_the_ticket_is_breached(self) -> None:
        assert (
            sla_state(facts(), local(2026, 10, 22, 12), CALENDAR) == SlaState.BREACHED
        )

    def test_a_hold_inside_the_deadline_pauses_the_sla(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 19, 11)
        )
        assert sla_state(on_hold, local(2026, 10, 19, 15), CALENDAR) == SlaState.PAUSED

    def test_a_hold_stays_paused_even_after_the_stored_deadline(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 19, 11)
        )
        assert sla_state(on_hold, local(2026, 10, 23, 12), CALENDAR) == SlaState.PAUSED

    def test_a_hold_that_starts_at_the_deadline_stays_breached(self) -> None:
        on_hold = facts(status=TicketStatus.ON_HOLD, on_hold_since=DUE)
        assert (
            sla_state(on_hold, local(2026, 10, 20, 12), CALENDAR) == SlaState.BREACHED
        )

    def test_a_hold_that_starts_after_the_deadline_stays_breached(self) -> None:
        on_hold = facts(
            status=TicketStatus.ON_HOLD, on_hold_since=local(2026, 10, 20, 12)
        )
        assert (
            sla_state(on_hold, local(2026, 10, 21, 12), CALENDAR) == SlaState.BREACHED
        )

    @pytest.mark.parametrize("status", [TicketStatus.RESOLVED, TicketStatus.CLOSED])
    def test_resolved_before_the_deadline_is_met(self, status: TicketStatus) -> None:
        resolved = facts(status=status, resolved_at=local(2026, 10, 19, 15))
        assert sla_state(resolved, local(2026, 10, 30, 12), CALENDAR) == SlaState.MET

    def test_resolved_exactly_at_the_deadline_is_met(self) -> None:
        assert (
            sla_state(
                facts(status=TicketStatus.RESOLVED, resolved_at=DUE), DUE, CALENDAR
            )
            == SlaState.MET
        )

    @pytest.mark.parametrize("status", [TicketStatus.RESOLVED, TicketStatus.CLOSED])
    def test_resolved_after_the_deadline_is_missed(self, status: TicketStatus) -> None:
        resolved = facts(status=status, resolved_at=local(2026, 10, 20, 11))
        assert sla_state(resolved, local(2026, 10, 30, 12), CALENDAR) == SlaState.MISSED

    def test_a_resolved_ticket_without_resolution_date_is_inconsistent(self) -> None:
        with pytest.raises(ValueError, match="resolución"):
            sla_state(facts(status=TicketStatus.RESOLVED), CREATED, CALENDAR)


def due_in_order(tickets: list[SlaFacts]) -> list[datetime]:
    return [ticket.due_at for ticket in sorted(tickets, key=queue_sort_key)]


class TestQueueSortKey:
    def test_running_tickets_go_by_deadline(self) -> None:
        later, sooner = (
            facts(due_at=local(2026, 10, 22, 10)),
            facts(due_at=local(2026, 10, 21, 10)),
        )
        assert due_in_order([later, sooner]) == [sooner.due_at, later.due_at]

    def test_tickets_on_hold_go_after_the_running_ones(self) -> None:
        on_hold = facts(status=TicketStatus.ON_HOLD, due_at=local(2026, 10, 19, 12))
        running = facts(due_at=local(2026, 10, 30, 10))
        assert due_in_order([on_hold, running]) == [running.due_at, on_hold.due_at]

    def test_tickets_on_hold_go_by_deadline_among_themselves(self) -> None:
        later = facts(status=TicketStatus.ON_HOLD, due_at=local(2026, 10, 22, 10))
        sooner = facts(status=TicketStatus.ON_HOLD, due_at=local(2026, 10, 21, 10))
        assert due_in_order([later, sooner]) == [sooner.due_at, later.due_at]

    def test_same_deadline_goes_by_age(self) -> None:
        newer = facts(created_at=local(2026, 10, 19, 12))
        older = facts(created_at=local(2026, 10, 19, 9))
        ordered = sorted([newer, older], key=queue_sort_key)
        assert [ticket.created_at for ticket in ordered] == [
            older.created_at,
            newer.created_at,
        ]
