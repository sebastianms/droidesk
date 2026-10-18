from typing import Annotated

from fastapi import Depends

from droidesk_api.core.config import SettingsDep
from droidesk_api.sla.calendar import BusinessCalendar


def get_calendar(settings: SettingsDep) -> BusinessCalendar:
    return BusinessCalendar(settings.timezone, settings.business_hours)


CalendarDep = Annotated[BusinessCalendar, Depends(get_calendar)]
