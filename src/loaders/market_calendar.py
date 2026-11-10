"""NYSE holidays (weekday closures), from exchange_calendars' XNYS calendar."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd


@lru_cache(maxsize=1)
def published_holidays() -> list[date]:
    """Weekday dates NYSE is closed, last year through next year."""
    import exchange_calendars as xcals

    cal = xcals.get_calendar("XNYS")
    y = date.today().year
    days = pd.bdate_range(f"{y - 1}-01-01", f"{y + 1}-12-31")
    sessions = set(cal.sessions_in_range(days[0], min(days[-1], cal.last_session)).date)
    return sorted(d.date() for d in days if d.date() not in sessions and pd.Timestamp(d) <= cal.last_session)


def not_a_session(day) -> str:
    """A reason when ``day`` is not an NYSE session, else ""."""
    from src.core.market_time import is_session

    d = pd.Timestamp(day).date()
    if is_session(d):
        return ""
    return "weekend" if d.weekday() >= 5 else "NYSE holiday"
