from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import count
from zoneinfo import ZoneInfo

MONDAY_TO_FRIDAY = frozenset(range(5))
WEEKDAYS = range(7)
ONE_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class BusinessHours:
    opens: time
    closes: time

    def __post_init__(self) -> None:
        if self.closes <= self.opens:
            raise ValueError(
                "El cierre de la jornada debe ser posterior a la apertura."
            )


@dataclass(frozen=True)
class BusinessCalendar:
    zone: ZoneInfo
    hours: BusinessHours
    workdays: frozenset[int] = MONDAY_TO_FRIDAY  # Monday = 0

    def __post_init__(self) -> None:
        if not self.workdays or not self.workdays <= set(WEEKDAYS):
            raise ValueError(
                "Debe haber al menos un día hábil, numerado de 0 (lunes) a 6 (domingo)."
            )

    @property
    def minutes_per_day(self) -> int:
        opening = datetime.combine(date.min, self.hours.opens)
        closing = datetime.combine(date.min, self.hours.closes)
        return (closing - opening) // ONE_MINUTE


def add_business_minutes(
    start_utc: datetime, minutes: int, calendar: BusinessCalendar
) -> datetime:
    """Instante en que se cumplen `minutes` de tiempo hábil desde `start_utc`."""
    _require_aware(start_utc)
    if minutes < 0:
        raise ValueError("Los minutos hábiles no pueden ser negativos.")
    start = start_utc.astimezone(UTC)
    remaining = timedelta(minutes=minutes)
    if not remaining:
        return start
    windows = _workday_windows(start, calendar)
    while True:
        opens_at, closes_at = next(windows)
        begin = max(opens_at, start)
        available = max(closes_at - begin, timedelta(0))
        if remaining <= available:
            return begin + remaining
        remaining -= available


def business_minutes_between(
    start_utc: datetime, end_utc: datetime, calendar: BusinessCalendar
) -> int:
    """Minutos hábiles completos entre dos instantes; 0 si `end_utc` no es posterior a `start_utc`."""
    _require_aware(start_utc)
    _require_aware(end_utc)
    start, end = start_utc.astimezone(UTC), end_utc.astimezone(UTC)
    elapsed = timedelta(0)
    for opens_at, closes_at in _workday_windows(start, calendar):
        if opens_at >= end:
            break
        elapsed += max(min(closes_at, end) - max(opens_at, start), timedelta(0))
    return elapsed // ONE_MINUTE


def _workday_windows(
    start: datetime, calendar: BusinessCalendar
) -> Iterator[tuple[datetime, datetime]]:
    first_day = start.astimezone(calendar.zone).date()
    for offset in count():
        day = first_day + timedelta(days=offset)
        if day.weekday() in calendar.workdays:
            yield (
                _local_instant(day, calendar.hours.opens, calendar),
                _local_instant(day, calendar.hours.closes, calendar),
            )


def _local_instant(day: date, at: time, calendar: BusinessCalendar) -> datetime:
    return datetime.combine(day, at, tzinfo=calendar.zone).astimezone(UTC)


def _require_aware(instant: datetime) -> None:
    if instant.utcoffset() is None:
        raise ValueError("La fecha debe tener zona horaria.")
