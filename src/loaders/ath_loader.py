"""All-time highs, from ``data/all_time_highs.csv`` (scripts/build_ath.py).

The price store starts in 2008; a stock's all-time high can be older (banks in
2007, technology in 2000). The file is built once from Yahoo's full history of
split-adjusted daily highs and then carried forward nightly as the max of
itself and the store, so it is a true all-time high for every member Yahoo has
full history for. Columns: Symbol, ATH, ATHDate, AsOf.
"""

from __future__ import annotations

import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FILE = os.path.join(ROOT, "data", "all_time_highs.csv")
_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}


def clear_snapshot_cache() -> None:
    _CACHE.clear()


def load_ath_snapshot(path: str | None = None) -> pd.DataFrame:
    p = path or FILE
    if not os.path.exists(p):
        return pd.DataFrame(columns=["Symbol", "ATH", "ATHDate", "AsOf"])
    m = os.path.getmtime(p)
    hit = _CACHE.get(p)
    if hit and hit[0] == m:
        return hit[1]
    df = pd.read_csv(p, dtype={"Symbol": str})
    _CACHE[p] = (m, df)
    return df


def ath_series(path: str | None = None) -> pd.Series:
    df = load_ath_snapshot(path)
    return pd.Series(pd.to_numeric(df["ATH"], errors="coerce").values, index=df["Symbol"], dtype=float)


def ath_date_series(path: str | None = None) -> pd.Series:
    df = load_ath_snapshot(path)
    return pd.Series(pd.to_datetime(df["ATHDate"], errors="coerce").values, index=df["Symbol"])
