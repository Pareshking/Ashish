import os

import numpy as np
import pandas as pd
import pytest

from src.loaders import price_store as ps


def _rows(dates, sym="AAA", start=100.0):
    d = pd.to_datetime(dates)
    c = start + np.arange(len(d), dtype=float)
    return pd.DataFrame({"Date": d, "Symbol": sym, "High": c + 1, "Low": c - 1, "Close": c, "Volume": 1000})


def test_file_for_partitions(tmp_path):
    today = pd.Timestamp("2026-11-10")
    assert ps.file_for(pd.Timestamp("2025-12-31"), today, str(tmp_path)).endswith("2025.parquet")
    assert ps.file_for(pd.Timestamp("2026-10-30"), today, str(tmp_path)).endswith("2026-10.parquet")
    assert ps.file_for(pd.Timestamp("2026-11-09"), today, str(tmp_path)).endswith(os.path.join("daily", "2026-11-09.parquet"))


def test_store_is_idempotent(tmp_path):
    today = pd.Timestamp("2026-11-10")
    df = _rows(["2025-12-30", "2025-12-31", "2026-10-30", "2026-11-09"])
    first = ps.store(df, today, str(tmp_path))
    assert len(first) == 3
    assert ps.store(df, today, str(tmp_path)) == []          # nothing changed, nothing written
    back = ps.read_long(str(tmp_path))
    assert len(back) == 4 and back["Close"].tolist() == [100, 101, 102, 103]


def test_roll_up_merges_closed_periods(tmp_path):
    df = _rows(["2026-11-27", "2026-11-30"])
    ps.store(df, pd.Timestamp("2026-11-30"), str(tmp_path))
    assert len(ps.files(str(tmp_path))["days"]) == 2
    ps.roll_up(pd.Timestamp("2026-12-01"), str(tmp_path))
    f = ps.files(str(tmp_path))
    assert f["days"] == [] and [os.path.basename(p) for p in f["months"]] == ["2026-11.parquet"]
    ps.roll_up(pd.Timestamp("2027-01-04"), str(tmp_path))
    f = ps.files(str(tmp_path))
    assert f["months"] == [] and [os.path.basename(p) for p in f["years"]] == ["2026.parquet"]
    assert len(ps.read_long(str(tmp_path))) == 2


def test_replace_symbol_rewrites_everywhere(tmp_path):
    today = pd.Timestamp("2026-11-10")
    ps.store(pd.concat([_rows(["2025-06-02", "2026-11-09"]), _rows(["2025-06-02"], sym="BBB")]), today, str(tmp_path))
    ps.replace_symbol("AAA", _rows(["2025-06-02", "2026-11-09"], start=50.0), today, str(tmp_path))
    back = ps.read_long(str(tmp_path))
    assert back[back.Symbol == "AAA"]["Close"].tolist() == [50, 51]
    assert back[back.Symbol == "BBB"]["Close"].tolist() == [100]


def test_adjusted_close_total_return_convention():
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"])
    close = pd.DataFrame({"AAA": [100.0, 100.0, 98.0, 99.0]}, index=idx)
    acts = pd.DataFrame({"Date": [pd.Timestamp("2026-01-06")], "Symbol": ["AAA"], "Dividend": [2.0], "Split": [0.0]})
    adj = ps.adjusted_close(close, acts)["AAA"]
    f = 98.0 / (98.0 + 2.0)          # ex-day return (98 + 2) / 100 - 1 = 0
    assert adj.tolist() == pytest.approx([100 * f, 100 * f, 98.0, 99.0])
    assert adj.iloc[2] / adj.iloc[1] - 1 == pytest.approx(0.0)


def test_large_special_dividend_is_paid_not_compounded():
    # KDP, 10 Jul 2018: $103.75 cash, close 123.66 -> 22.19; the holder made +1.8%.
    idx = pd.to_datetime(["2018-07-09", "2018-07-10"])
    close = pd.DataFrame({"KDP": [123.66, 22.19]}, index=idx)
    acts = pd.DataFrame({"Date": [idx[1]], "Symbol": ["KDP"], "Dividend": [103.75], "Split": [0.0]})
    adj = ps.adjusted_close(close, acts)["KDP"]
    assert adj.iloc[1] / adj.iloc[0] - 1 == pytest.approx((22.19 + 103.75) / 123.66 - 1)


def test_spin_off_written_as_split_and_dividend_counts_once():
    # DHR, 5 Jul 2016: Yahoo writes Fortive as split 1.319 AND dividend 24.56;
    # its split-adjusted close is already continuous (68.77 -> 71.28).
    idx = pd.to_datetime(["2016-07-01", "2016-07-05"])
    close = pd.DataFrame({"DHR": [68.77, 71.28]}, index=idx)
    acts = pd.DataFrame({"Date": [idx[1]], "Symbol": ["DHR"], "Dividend": [24.56], "Split": [1.319]})
    adj = ps.adjusted_close(close, acts)["DHR"]
    assert adj.iloc[1] / adj.iloc[0] - 1 == pytest.approx(71.28 / 68.77 - 1)
    # A real split ratio beside a dividend is two events: both apply.
    acts2 = acts.assign(Split=[2.0])
    assert ps.adjusted_close(close, acts2)["DHR"].iloc[0] < 68.77


def test_clean_ratios():
    for r in (2.0, 0.5, 1.5, 0.1, 3.0, 4 / 3, 1.25, 0.05, 20.0):
        assert ps.is_clean_ratio(r)
    for r in (1.319, 0.8757, 2.545, 1.0241, 1.193):
        assert not ps.is_clean_ratio(r)


def test_adjusted_close_without_actions_is_close():
    close = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    assert ps.adjusted_close(close, pd.DataFrame(columns=ps.ACTION_COLS)).equals(close)


def test_read_wide_equals_long_pivot(tmp_path):
    today = pd.Timestamp("2026-11-10")
    df = pd.concat([_rows(["2025-12-30", "2026-10-30", "2026-11-09"]), _rows(["2025-12-31", "2026-11-09"], sym="BBB", start=5.0)])
    ps.store(df, today, str(tmp_path))
    w = ps.read_wide(["Close", "High"], str(tmp_path), symbols=["BBB", "AAA"])
    ref = ps.wide(ps.read_long(str(tmp_path)), "Close")[["BBB", "AAA"]].astype("float64")
    assert list(w["Close"].columns) == ["BBB", "AAA"]
    assert w["Close"].equals(ref)
    assert ps.read_wide(["Close"], str(tmp_path), start="2026-01-01")["Close"].index.min() == pd.Timestamp("2026-10-30")
