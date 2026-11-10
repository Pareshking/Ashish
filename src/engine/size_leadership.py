"""Which size of company is leading: S&P 500 (large), S&P 400 (mid) and S&P 600
(small) against the S&P 1500 over one, three and six months.

Price returns of the three price indices (Yahoo ^GSPC, ^SP400, ^SP600) against
the S&P 1500 ETF's price (SPTM, no dividends), so all four are on the same basis.
Every window starts on the same session for every index (the ranking's own
calendar rule, `calendar_start_positions`).

`cross_check`: the levels and the benchmark come from one vendor here, so the
check is that each index's latest session is the benchmark's latest session
(a stale index would otherwise be compared across different windows).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.engine.calendar_momentum import calendar_start_positions

INDICES = (
    ("sp500", "S&P 500"),
    ("sp400", "S&P 400"),
    ("sp600", "S&P 600"),
)
WINDOWS = (1, 3, 6)
CHECK_TOLERANCE = 0.001


@dataclass(frozen=True)
class SizeLeadership:
    table: pd.DataFrame          # one row per index: "<w>M" return and "<w>M vs 500"
    starts: dict[int, pd.Timestamp]
    end: pd.Timestamp
    sources: tuple[str, ...]


def closes(levels: pd.DataFrame) -> pd.DataFrame:
    """The long index-level file (date, index, close) as one column per index."""
    frame = levels.assign(date=pd.to_datetime(levels["date"]).dt.normalize())
    wide = frame.pivot_table(index="date", columns="index", values="close", aggfunc="last")
    return wide.sort_index()


def cross_check(levels: pd.DataFrame, benchmark: pd.Series) -> tuple[bool, str]:
    """Do all size indices reach the benchmark's latest session?"""
    wide = closes(levels)
    bench = pd.to_numeric(benchmark, errors="coerce").dropna()
    if bench.empty:
        return False, "no benchmark series"
    last = pd.Timestamp(bench.index.max()).normalize()
    behind = [name for key, name in INDICES
              if key not in wide or wide[key].dropna().empty or wide[key].dropna().index.max() < last]
    if behind:
        return False, f"{', '.join(behind)} not at the benchmark's latest session ({last.date()})"
    return True, f"all size indices at {last.date()} (Yahoo; one source, not cross-checked)"


def size_leadership(levels: pd.DataFrame, nifty500: pd.Series) -> SizeLeadership | None:
    wide = closes(levels)
    keys = [k for k, _ in INDICES if k in wide]
    if len(keys) != len(INDICES):
        return None
    n500 = pd.to_numeric(nifty500, errors="coerce").dropna()
    n500.index = pd.to_datetime(n500.index).normalize()
    joined = wide[keys].join(n500.rename("bench_tr"), how="inner").dropna()
    if len(joined) < 2:
        return None
    idx = pd.DatetimeIndex(joined.index)
    end = idx[-1]
    rows: dict[str, dict[str, float]] = {name: {} for _, name in INDICES}
    rows["S&P 1500"] = {}
    starts: dict[int, pd.Timestamp] = {}
    for w in WINDOWS:
        pos = int(calendar_start_positions(idx, w)[-1])
        if pos >= len(idx) - 1:
            continue
        start = idx[pos]
        starts[w] = start
        r500 = joined.at[end, "bench_tr"] / joined.at[start, "bench_tr"] - 1
        rows["S&P 1500"][f"{w}M"] = r500
        for key, name in INDICES:
            r = joined.at[end, key] / joined.at[start, key] - 1
            rows[name][f"{w}M"] = r
            # A difference in points, as on Sectors (audit, 8 Nov 2026: the ratio
            # here and the difference there gave two figures for one comparison).
            rows[name][f"{w}M vs 500"] = r - r500
    sources = tuple(sorted(set(levels.get("source", pd.Series(dtype=str)).dropna().astype(str))))
    return SizeLeadership(pd.DataFrame(rows).T, starts, end, sources)


def headline(result: SizeLeadership) -> str:
    """One plain sentence: who leads over the shortest and the longest window."""
    t = result.table.drop(index="S&P 1500", errors="ignore")
    parts = []
    for w in (min(result.starts), max(result.starts)) if result.starts else ():
        col = f"{w}M vs 500"
        if col in t:
            parts.append(f"{t[col].idxmax()} leads over {w} month{'s' if w > 1 else ''}")
    return "; ".join(dict.fromkeys(parts)) + "." if parts else ""
