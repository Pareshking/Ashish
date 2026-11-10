from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.core import market_time as mt

NY = ZoneInfo("America/New_York")


def test_nyse_holidays_and_early_close():
    assert not mt.is_session(date(2026, 11, 26))          # Thanksgiving
    assert mt.is_session(date(2026, 11, 27))              # half day
    assert mt.session_close(date(2026, 11, 27)).hour == 13
    assert not mt.is_session(date(2026, 12, 25))
    assert not mt.is_session(date(2026, 11, 14))          # Saturday


def test_download_waits_for_close_plus_slack():
    d = date(2026, 11, 10)
    assert not mt.session_is_downloadable(d, now=datetime(2026, 11, 10, 17, 29, tzinfo=NY))
    assert mt.session_is_downloadable(d, now=datetime(2026, 11, 10, 17, 30, tzinfo=NY))
    # Early close: 13:00 + 90 min
    assert mt.session_is_downloadable(date(2026, 11, 27), now=datetime(2026, 11, 27, 14, 30, tzinfo=NY))


def test_utc_reference_is_converted():
    # 22:00 UTC on 10 Nov 2026 is 17:00 EST: not yet downloadable.
    utc = datetime(2026, 11, 10, 22, 0, tzinfo=ZoneInfo("UTC"))
    assert mt.last_downloadable_session(now=utc) == date(2026, 11, 9)


def test_trading_days_behind_counts_sessions():
    assert mt.trading_days_behind(date(2026, 11, 6), today=date(2026, 11, 9)) == 1
    assert mt.trading_days_behind(date(2026, 11, 25), today=date(2026, 11, 27)) == 1
