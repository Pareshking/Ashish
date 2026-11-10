import pandas as pd

from scripts import sync_prices as sp
from src.loaders import price_store as ps


def _r(sym, dates, closes):
    return ps.normalise(pd.DataFrame({"Date": pd.to_datetime(dates), "Symbol": sym,
                                      "High": closes, "Low": closes, "Close": closes, "Volume": 1}))


def test_restated_detects_split_rebasing():
    stored = pd.concat([_r("A", ["2026-11-05", "2026-11-06"], [100, 102]), _r("B", ["2026-11-05", "2026-11-06"], [10, 11])])
    fresh = pd.concat([_r("A", ["2026-11-05", "2026-11-06"], [50, 51]), _r("B", ["2026-11-05", "2026-11-06"], [10, 11.001])])
    assert sp.restated(stored, fresh) == ["A"]


def test_settled_only_drops_holiday_and_future():
    rows = _r("A", ["2026-11-25", "2026-11-26", "2026-11-27", "2026-11-30"], [1, 2, 3, 4])
    out = sp.settled_only(rows, pd.Timestamp("2026-11-27").date())
    assert [d.day for d in out["Date"]] == [25, 27]          # 26 Thanksgiving, 30 not settled


def test_thin_new_session_is_held_back():
    rows = pd.concat([_r(s, ["2026-11-09"], [1]) for s in "ABCDEFGHIJ"] + [_r("A", ["2026-11-10"], [1])])
    kept, notes = sp.coverage_ok(rows, 10)
    assert set(kept["Date"].dt.day) == {9} and "held back" in notes[0]
