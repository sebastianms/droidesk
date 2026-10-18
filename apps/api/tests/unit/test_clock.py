from datetime import UTC, datetime, timedelta

from droidesk_api.core.clock import SystemClock, get_clock


def test_system_clock_gives_the_current_time() -> None:
    assert abs(SystemClock().now() - datetime.now(UTC)) < timedelta(seconds=5)


def test_system_clock_time_has_a_timezone() -> None:
    assert SystemClock().now().utcoffset() == timedelta(0)


def test_the_default_clock_is_the_system_clock() -> None:
    assert isinstance(get_clock(), SystemClock)
