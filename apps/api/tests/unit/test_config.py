import os
from datetime import time
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from droidesk_api.core.config import DatabaseSettings, Settings, get_settings
from droidesk_api.sla.calendar import BusinessHours

SECRET = "s" * 32


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("DROIDESK_")]:
        monkeypatch.delenv(name)


@pytest.fixture
def secret_in_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DROIDESK_JWT_SECRET", SECRET)


@pytest.mark.usefixtures("secret_in_environment")
class TestDefaults:
    def test_database_lives_in_the_docker_volume(self) -> None:
        assert Settings().database_url == "sqlite:////data/droidesk.db"

    def test_demo_data_is_on(self) -> None:
        assert Settings().seed_demo_data is True

    def test_timezone_is_santiago(self) -> None:
        assert Settings().timezone == ZoneInfo("America/Santiago")

    def test_business_hours_are_nine_to_six(self) -> None:
        assert Settings().business_hours == BusinessHours(
            opens=time(9, 0), closes=time(18, 0)
        )


@pytest.mark.usefixtures("secret_in_environment")
class TestEnvironment:
    def test_reads_variables_with_the_droidesk_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DROIDESK_DATABASE_URL", "sqlite:///other.db")
        assert Settings().database_url == "sqlite:///other.db"

    def test_reads_the_demo_data_switch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DROIDESK_SEED_DEMO_DATA", "false")
        assert Settings().seed_demo_data is False

    def test_reads_the_timezone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DROIDESK_TIMEZONE", "Europe/Madrid")
        assert Settings().timezone == ZoneInfo("Europe/Madrid")

    def test_reads_the_business_hours(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DROIDESK_BUSINESS_HOURS", "08:30-17:45")
        assert Settings().business_hours == BusinessHours(
            opens=time(8, 30), closes=time(17, 45)
        )

    def test_ignores_unrelated_droidesk_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DROIDESK_WEB_PORT", "8080")
        assert Settings().database_url

    def test_hides_the_secret_when_printed(self) -> None:
        assert SECRET not in repr(Settings())


class TestJwtSecret:
    def test_is_required(self) -> None:
        with pytest.raises(ValidationError, match="jwt_secret"):
            Settings()

    def test_needs_at_least_32_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DROIDESK_JWT_SECRET", "s" * 31)
        with pytest.raises(ValidationError, match="al menos 32 bytes"):
            Settings()

    def test_a_rejected_secret_is_not_printed_in_the_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        short_secret = "abc-short-secret"
        monkeypatch.setenv("DROIDESK_JWT_SECRET", short_secret)
        with pytest.raises(ValidationError) as error:
            Settings()
        assert short_secret not in str(error.value)

    def test_accepts_exactly_32_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DROIDESK_JWT_SECRET", SECRET)
        assert Settings().jwt_secret.get_secret_value() == SECRET

    def test_counts_bytes_not_characters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DROIDESK_JWT_SECRET", "ñ" * 16)
        assert Settings().jwt_secret.get_secret_value() == "ñ" * 16


@pytest.mark.usefixtures("secret_in_environment")
class TestBusinessHours:
    @pytest.mark.parametrize("raw", ["18:00-09:00", "09:00-09:00"])
    def test_closing_must_be_after_opening(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.setenv("DROIDESK_BUSINESS_HOURS", raw)
        with pytest.raises(ValidationError, match="posterior a la apertura"):
            Settings()

    @pytest.mark.parametrize(
        "raw", ["9-18", "09:00", "09:00-25:00", "09:00 a 18:00", ""]
    )
    def test_rejects_other_formats(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.setenv("DROIDESK_BUSINESS_HOURS", raw)
        with pytest.raises(ValidationError, match="business_hours"):
            Settings()


@pytest.mark.usefixtures("secret_in_environment")
def test_rejects_an_unknown_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DROIDESK_TIMEZONE", "Mars/Base")
    with pytest.raises(ValidationError, match="timezone"):
        Settings()


def test_database_settings_do_not_need_the_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DROIDESK_DATABASE_URL", "sqlite:///migrations.db")
    assert DatabaseSettings().database_url == "sqlite:///migrations.db"


@pytest.mark.usefixtures("secret_in_environment")
def test_get_settings_builds_them_once() -> None:
    assert get_settings() is get_settings()
