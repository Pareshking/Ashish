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


def test_adjusted_close_matches_yahoo_method():
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"])
    close = pd.DataFrame({"AAA": [100.0, 100.0, 98.0, 99.0]}, index=idx)
    acts = pd.DataFrame({"Date": [pd.Timestamp("2026-01-06")], "Symbol": ["AAA"], "Dividend": [2.0], "Split": [0.0]})
    adj = ps.adjusted_close(close, acts)["AAA"]
    f = 1 - 2.0 / 100.0
    assert adj.tolist() == pytest.approx([100 * f, 100 * f, 98.0, 99.0])


def test_adjusted_close_without_actions_is_close():
    close = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    assert ps.adjusted_close(close, pd.DataFrame(columns=ps.ACTION_COLS)).equals(close)
