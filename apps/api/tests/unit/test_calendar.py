from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from droidesk_api.sla.calendar import (
    BusinessCalendar,
    BusinessHours,
    add_business_minutes,
    business_minutes_between,
)

SANTIAGO = ZoneInfo("America/Santiago")
WORKDAY = BusinessHours(opens=time(9, 0), closes=time(18, 0))
CALENDAR = BusinessCalendar(zone=SANTIAGO, hours=WORKDAY)

HOUR = 60
DAY = 9 * HOUR


def local(
    year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0
) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=SANTIAGO).astimezone(
        UTC
    )


class TestAddBusinessMinutes:
    def test_alta_inside_the_workday_is_due_the_next_day_at_the_same_hour(self) -> None:
        assert add_business_minutes(local(2026, 10, 19, 10), DAY, CALENDAR) == local(
            2026, 10, 20, 10
        )

    def test_alta_created_friday_night_is_due_monday_at_closing(self) -> None:
        assert add_business_minutes(local(2026, 10, 23, 20), DAY, CALENDAR) == local(
            2026, 10, 26, 18
        )

    def test_critica_crossing_the_closing_continues_next_morning(self) -> None:
        assert add_business_minutes(
            local(2026, 10, 19, 16), 4 * HOUR, CALENDAR
        ) == local(2026, 10, 20, 11)

    def test_media_crossing_the_weekend(self) -> None:
        assert add_business_minutes(
            local(2026, 10, 22, 12), 3 * DAY, CALENDAR
        ) == local(2026, 10, 27, 12)

    def test_baja_from_monday_opening_is_due_friday_at_closing(self) -> None:
        assert add_business_minutes(local(2026, 10, 19, 9), 5 * DAY, CALENDAR) == local(
            2026, 10, 23, 18
        )

    def test_paused_alta_adds_the_wait_to_the_budget(self) -> None:
        paused_budget = DAY + 4 * HOUR
        assert add_business_minutes(
            local(2026, 10, 19, 10), paused_budget, CALENDAR
        ) == local(2026, 10, 20, 14)

    def test_zero_minutes_returns_the_start(self) -> None:
        start = local(2026, 10, 24, 12)
        assert add_business_minutes(start, 0, CALENDAR) == start

    def test_start_before_opening_waits_for_the_opening(self) -> None:
        assert add_business_minutes(local(2026, 10, 19, 7), HOUR, CALENDAR) == local(
            2026, 10, 19, 10
        )

    def test_start_at_closing_waits_for_next_opening(self) -> None:
        assert add_business_minutes(local(2026, 10, 19, 18), HOUR, CALENDAR) == local(
            2026, 10, 20, 10
        )

    def test_start_on_saturday_waits_for_monday(self) -> None:
        assert add_business_minutes(local(2026, 10, 24, 12), HOUR, CALENDAR) == local(
            2026, 10, 26, 10
        )

    def test_deadline_exactly_at_closing_stays_in_the_same_day(self) -> None:
        assert add_business_minutes(local(2026, 10, 19, 17), HOUR, CALENDAR) == local(
            2026, 10, 19, 18
        )

    def test_deadline_exactly_at_closing_on_friday_does_not_jump_to_monday(
        self,
    ) -> None:
        assert add_business_minutes(local(2026, 10, 23, 9), DAY, CALENDAR) == local(
            2026, 10, 23, 18
        )

    def test_friday_afternoon_continues_on_monday(self) -> None:
        assert add_business_minutes(
            local(2026, 10, 23, 17), 2 * HOUR, CALENDAR
        ) == local(2026, 10, 26, 10)

    def test_keeps_the_seconds_of_the_start(self) -> None:
        assert add_business_minutes(
            local(2026, 10, 19, 10, 0, 30), HOUR, CALENDAR
        ) == local(2026, 10, 19, 11, 0, 30)

    def test_result_is_expressed_in_utc(self) -> None:
        result = add_business_minutes(local(2026, 10, 19, 10), HOUR, CALENDAR)
        assert result.utcoffset() == timedelta(0)

    def test_accepts_a_start_in_another_zone(self) -> None:
        start = local(2026, 10, 19, 10).astimezone(ZoneInfo("Asia/Tokyo"))
        assert add_business_minutes(start, HOUR, CALENDAR) == local(2026, 10, 19, 11)

    def test_summer_time_end_shifts_the_monday_opening_in_utc(self) -> None:
        # 2026-04-04: Santiago pasa de UTC-3 a UTC-4. El lunes 09:00 local ya es 13:00 UTC.
        result = add_business_minutes(local(2026, 4, 3, 17), 2 * HOUR, CALENDAR)
        assert result == datetime(2026, 4, 6, 14, 0, tzinfo=UTC)

    def test_summer_time_start_shifts_the_monday_opening_in_utc(self) -> None:
        # 2026-09-05: Santiago pasa de UTC-4 a UTC-3. El lunes 09:00 local ya es 12:00 UTC.
        result = add_business_minutes(local(2026, 9, 4, 17), 2 * HOUR, CALENDAR)
        assert result == datetime(2026, 9, 7, 13, 0, tzinfo=UTC)

    def test_rejects_a_start_without_timezone(self) -> None:
        naive = datetime(2026, 10, 19, 10)  # noqa: DTZ001
        with pytest.raises(ValueError, match="zona horaria"):
            add_business_minutes(naive, HOUR, CALENDAR)

    def test_rejects_negative_minutes(self) -> None:
        with pytest.raises(ValueError, match="negativ"):
            add_business_minutes(local(2026, 10, 19, 10), -1, CALENDAR)

    def test_follows_a_custom_calendar(self) -> None:
        saturdays_too = BusinessCalendar(
            zone=ZoneInfo("UTC"),
            hours=BusinessHours(opens=time(8, 0), closes=time(12, 0)),
            workdays=frozenset(range(6)),
        )
        start = datetime(2026, 10, 24, 11, 0, tzinfo=UTC)  # sábado
        assert add_business_minutes(start, 2 * HOUR, saturdays_too) == datetime(
            2026, 10, 26, 9, 0, tzinfo=UTC
        )


class TestBusinessMinutesBetween:
    def test_same_instant_is_zero(self) -> None:
        instant = local(2026, 10, 19, 10)
        assert business_minutes_between(instant, instant, CALENDAR) == 0

    def test_end_before_start_is_zero(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 12), local(2026, 10, 19, 10), CALENDAR
            )
            == 0
        )

    def test_inside_one_workday(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 11), local(2026, 10, 19, 15), CALENDAR
            )
            == 4 * HOUR
        )

    def test_across_the_closing(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 17), local(2026, 10, 20, 10), CALENDAR
            )
            == 2 * HOUR
        )

    def test_overnight_is_not_counted(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 18), local(2026, 10, 20, 9), CALENDAR
            )
            == 0
        )

    def test_weekend_is_not_counted(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 24, 0), local(2026, 10, 25, 23), CALENDAR
            )
            == 0
        )

    def test_friday_night_to_monday_opening_is_zero(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 23, 20), local(2026, 10, 26, 9), CALENDAR
            )
            == 0
        )

    def test_a_full_business_week(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 9), local(2026, 10, 23, 18), CALENDAR
            )
            == 5 * DAY
        )

    def test_across_the_end_of_summer_time(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 4, 3, 17), local(2026, 4, 6, 10), CALENDAR
            )
            == 2 * HOUR
        )

    def test_across_the_start_of_summer_time(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 9, 4, 17), local(2026, 9, 7, 10), CALENDAR
            )
            == 2 * HOUR
        )

    def test_discards_the_incomplete_minute(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 10), local(2026, 10, 19, 10, 0, 59), CALENDAR
            )
            == 0
        )

    def test_counts_the_complete_minute(self) -> None:
        assert (
            business_minutes_between(
                local(2026, 10, 19, 10), local(2026, 10, 19, 10, 1), CALENDAR
            )
            == 1
        )

    def test_rejects_an_end_without_timezone(self) -> None:
        naive = datetime(2026, 10, 19, 11)  # noqa: DTZ001
        with pytest.raises(ValueError, match="zona horaria"):
            business_minutes_between(local(2026, 10, 19, 10), naive, CALENDAR)


STARTS = [
    local(2026, 10, 19, 10),  # lunes dentro de la jornada
    local(2026, 10, 19, 9),  # lunes a la apertura
    local(2026, 10, 19, 18),  # lunes al cierre
    local(2026, 10, 23, 20),  # viernes de noche
    local(2026, 10, 24, 12),  # sábado
    local(2026, 4, 3, 16, 30, 15),  # antes del fin del horario de verano
    local(2026, 9, 4, 17, 45),  # antes del inicio del horario de verano
]
BUDGETS = [0, 1, 59, HOUR, 4 * HOUR, DAY, 3 * DAY + 17, 5 * DAY]


@pytest.mark.parametrize("budget", BUDGETS)
@pytest.mark.parametrize("start", STARTS)
def test_between_start_and_start_plus_minutes_gives_back_the_minutes(
    start: datetime, budget: int
) -> None:
    assert (
        business_minutes_between(
            start, add_business_minutes(start, budget, CALENDAR), CALENDAR
        )
        == budget
    )


class TestBusinessHours:
    def test_closing_must_be_after_opening(self) -> None:
        with pytest.raises(ValueError, match="cierre"):
            BusinessHours(opens=time(18, 0), closes=time(9, 0))

    def test_closing_equal_to_opening_is_invalid(self) -> None:
        with pytest.raises(ValueError, match="cierre"):
            BusinessHours(opens=time(9, 0), closes=time(9, 0))


class TestBusinessCalendar:
    def test_minutes_per_day_is_the_length_of_the_workday(self) -> None:
        assert CALENDAR.minutes_per_day == DAY

    def test_default_workdays_are_monday_to_friday(self) -> None:
        assert CALENDAR.workdays == frozenset({0, 1, 2, 3, 4})

    def test_needs_at_least_one_workday(self) -> None:
        with pytest.raises(ValueError, match="día hábil"):
            BusinessCalendar(
                zone=SANTIAGO,
                hours=WORKDAY,
                workdays=frozenset(),
            )

    def test_workdays_must_be_weekday_numbers(self) -> None:
        with pytest.raises(ValueError, match="día hábil"):
            BusinessCalendar(
                zone=SANTIAGO,
                hours=WORKDAY,
                workdays=frozenset({7}),
            )
