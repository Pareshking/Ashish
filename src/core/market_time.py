"""US-market time helpers.

Every "today" in this application is a question about a NYSE trading day, so
it is answered in America/New_York, never in the server's timezone. Streamlit
Cloud and GitHub Actions run in UTC: from 19:00/20:00 UTC (EST/EDT) to midnight
the UTC date is already tomorrow in New York's terms for the purpose of "has
today's session closed", and before 09:30 NY the UTC date can be today while
New York's session has not opened.

The NYSE calendar (holidays and 13:00 early closes) comes from the
``exchange_calendars`` package (XNYS). Unlike NSE, NYSE publishes its holiday
schedule years ahead and does not hold surprise weekend sessions, so a
published calendar is safe here where Paresh had to learn sessions from the
exchange's own files.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd

NY_TZ = ZoneInfo("America/New_York")

# The regular close is 16:00 ET (13:00 on early-close days). Yahoo's daily bar
# is final a few minutes after the closing auction prints; consolidated volume
# keeps being restated for about an hour. A row dated today is in progress
# until SESSION_SETTLES after that session's own close.
SESSION_SETTLES_AFTER = timedelta(minutes=30)

# When a download is worth making: close + 90 minutes. Earlier answers exist
# but volume (and, on a corporate-action day, the split-adjusted history) is
# still being revised.
DOWNLOAD_SETTLES_AFTER = timedelta(minutes=90)

# By this New York time on the next calendar day a session's closes are overdue
# in the published files, not merely late (nightly sync plus GitHub's start
# delay, which has reached several hours).
PRICES_DUE = time(9, 0)


@lru_cache(maxsize=1)
def _calendar():
    import exchange_calendars as xcals

    return xcals.get_calendar("XNYS")


def ny_now() -> datetime:
    """Current time in New York, timezone-aware."""
    return datetime.now(NY_TZ)


def ny_today() -> date:
    """Today's date as the New York market sees it."""
    return ny_now().date()


# Names the ported engine and pages call (Paresh's were ist_*).
market_now = ny_now
market_today = ny_today


def is_session(day: date) -> bool:
    """Was (or will) ``day`` be a NYSE trading session?"""
    cal = _calendar()
    ts = pd.Timestamp(day)
    if ts < cal.first_session or ts > cal.last_session:
        return day.weekday() < 5
    return bool(cal.is_session(ts))


def not_a_session(day: date) -> bool:
    return not is_session(day)


def session_close(day: date) -> datetime:
    """The session's scheduled close in New York time (13:00 on early closes)."""
    cal = _calendar()
    ts = pd.Timestamp(day)
    if cal.is_session(ts):
        return cal.session_close(ts).tz_convert(NY_TZ).to_pydatetime()
    return datetime.combine(day, time(16, 0), tzinfo=NY_TZ)


def recent_trading_days(count: int = 6, *, as_of: date | None = None,
                        max_lookback_days: int = 21, **_ignored) -> list[date]:
    """Most recent NYSE sessions on or before ``as_of``, newest first."""
    if count <= 0:
        return []
    cursor = as_of or ny_today()
    days: list[date] = []
    for offset in range(max_lookback_days):
        day = cursor - timedelta(days=offset)
        if is_session(day):
            days.append(day)
            if len(days) >= count:
                break
    return days


def trading_days_behind(as_of: date, *, today: date | None = None, horizon: int = 30) -> int | None:
    """How many sessions old ``as_of`` is (0 = the latest session). None if
    outside the horizon or in the future. ``as_of`` is never itself discarded,
    so a calendar error can only shorten the count, not hide a real session."""
    days = recent_trading_days(horizon, as_of=today or ny_today(), max_lookback_days=horizon * 2)
    if as_of not in days and as_of <= (today or ny_today()):
        days = sorted(set(days) | {as_of}, reverse=True)
    try:
        return days.index(as_of)
    except ValueError:
        return None


def session_is_complete(day: date, *, now: datetime | None = None) -> bool:
    """Has ``day``'s daily bar stopped moving?"""
    reference = (now or ny_now()).astimezone(NY_TZ)
    today = reference.date()
    if day < today:
        return True
    if day > today:
        return False
    return reference >= session_close(day) + SESSION_SETTLES_AFTER


def session_is_downloadable(day: date, *, now: datetime | None = None) -> bool:
    """Is ``day``'s bar worth requesting from the vendor yet?"""
    reference = (now or ny_now()).astimezone(NY_TZ)
    today = reference.date()
    if day > today:
        return False
    if day < today:
        return True
    return reference >= session_close(day) + DOWNLOAD_SETTLES_AFTER


def last_downloadable_session(*, now: datetime | None = None) -> date | None:
    reference = (now or ny_now()).astimezone(NY_TZ)
    for day in recent_trading_days(count=10, as_of=reference.date()):
        if session_is_downloadable(day, now=reference):
            return day
    return None


def last_due_session(*, now: datetime | None = None) -> date | None:
    """Newest session whose closes the published files should hold by now."""
    reference = (now or ny_now()).astimezone(NY_TZ)
    for day in recent_trading_days(count=10, as_of=reference.date(), max_lookback_days=30):
        if reference >= datetime.combine(day + timedelta(days=1), PRICES_DUE, tzinfo=NY_TZ):
            return day
    return None
