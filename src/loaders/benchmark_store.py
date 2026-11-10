"""Benchmark closes, from ``data/benchmarks.csv`` (written by scripts/sync_prices.py).

Columns: SPTM (S&P 1500 ETF close), SPTM_TR (its dividend-adjusted close: the
benchmark), ^GSPC, ^SP400, ^SP600 (S&P price indices, for size leadership).
``"^SP1500"`` is accepted as a name for the benchmark.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FILE = Path(__file__).resolve().parents[2] / "data" / "benchmarks.csv"
ALIASES = {"^SP1500": "SPTM_TR", "SP1500": "SPTM_TR", "BENCHMARK": "SPTM_TR"}
_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}


def read(path: Path = FILE) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    m = p.stat().st_mtime
    hit = _CACHE.get(str(p))
    if hit and hit[0] == m:
        return hit[1]
    df = pd.read_csv(p, index_col=0, parse_dates=True).sort_index()
    df.index.name = "Date"
    _CACHE[str(p)] = (m, df)
    return df


def _period_start(last: pd.Timestamp, period: str | None) -> pd.Timestamp | None:
    if not period or period == "max":
        return None
    n, unit = int(period[:-1] or 0), period[-1].lower()
    if unit == "y":
        return last - pd.DateOffset(years=n)
    if unit == "m":
        return last - pd.DateOffset(months=n)
    if unit == "d":
        return last - pd.Timedelta(days=n)
    raise ValueError(f"unknown period {period!r}")


def history(period: str = "2y", symbol: str = "SPTM_TR", path: Path = FILE) -> pd.Series:
    df = read(path)
    col = ALIASES.get(symbol, symbol)
    if df.empty or col not in df:
        return pd.Series(dtype=float, name=symbol)
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return s.rename(symbol)
    start = _period_start(s.index[-1], period)
    if start is not None:
        s = s[s.index >= start]
    return s.rename(symbol)
