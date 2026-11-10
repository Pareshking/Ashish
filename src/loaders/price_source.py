"""The price frames the engine scores, from the committed US store.

One source (Yahoo, via scripts/sync_prices.py into data/prices/). Paresh chose
between Screener, NSE and Yahoo here; the contract it handed the app is kept --
``PriceFrames`` with adjusted close, close, high, low and volume -- so the
ported pipeline and pages read the same fields.

Two windows are served, because memory on Streamlit Cloud is ~1 GB:
  * the RANKING frames: the last RANKING_YEARS of every field (the 12-month
    lookback, the 52-week high and a 300-day EMA need ~14 months);
  * the DEEP adjusted close from DEEP_START, for the backtest and the record.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.loaders import price_store as ps

RANKING_YEARS = 3
# A member whose latest close is this many sessions behind the store is not
# ranked: it was acquired or delisted while still on the Wikipedia list.
LAST_LAG = 5
DEEP_START = "2010-01-01"
_DISPLAY_NAMES = {"yahoo": "Yahoo Finance"}
MOMENTUM_MONTHS = [1, 3, 6, 9, 12]


@dataclass
class PriceFrames:
    """What the engine needs, plus what the caller must say out loud."""

    adj_close: pd.DataFrame
    close: pd.DataFrame
    high: pd.DataFrame | None
    low: pd.DataFrame | None
    volume: pd.DataFrame
    source: str = "yahoo"
    intraday: bool = True
    notes: list[str] = field(default_factory=list)
    weekly_fill: dict | None = None
    middle_errors: list[str] = field(default_factory=list)

    @property
    def high_basis(self) -> str:
        return "intraday highs" if self.intraday else "closing prices"


def reaches_longest_lookback(index: pd.Index, months: int | None = None) -> bool:
    """Would the longest horizon fit in this history?"""
    if index is None or len(index) < 2:
        return False
    want = int(months or max(MOMENTUM_MONTHS))
    dates = pd.DatetimeIndex(index).normalize()
    return bool(dates[-1] - pd.DateOffset(months=want) >= dates[0])


def display_name(source: str | None) -> str:
    key = str(source or "").strip().lower()
    if not key:
        return ""
    return _DISPLAY_NAMES.get(key, key.replace("_", " ").title())


def preferred() -> str:
    return "yahoo"


def _restrict(frame: pd.DataFrame, symbols) -> pd.DataFrame:
    cols = [s for s in symbols if s in frame.columns]
    return frame[cols]


def former_members_of_main_index() -> list[str]:
    """Every symbol the main index's point-in-time timeline ever lists."""
    try:
        from src.engine import index_universe as iu
        from src.engine import systems

        h = systems.membership_for(systems.SYSTEM_750)
        ever = iu.ever_members(h) if h else set()
        al = (h or {}).get("aliases") or {}
        return sorted(ever | {al[s]["new_symbol"] for s in ever if s in al})
    except Exception:  # noqa: BLE001 - no timeline: today's members only
        return []


def load(symbols, *, start: str | None = None, prices_dir: str = ps.PRICES_DIR) -> tuple[PriceFrames | None, pd.DataFrame | None]:
    """(ranking frames, deep adjusted close) for ``symbols``; (None, None)
    when the store is empty or cannot reach the 12-month lookback."""
    symbols = list(symbols)
    actions = ps.read_actions()
    # The deep history also carries every stock that was in the main index at
    # some month-end (under today's ticker where it was renamed): the record and
    # the backtest score each month on the index as it stood, and a member that
    # has since left must still have its prices, or the pool is the survivors.
    deep_syms = list(dict.fromkeys(symbols + former_members_of_main_index()))
    deep_close = ps.read_wide(["Close"], prices_dir, start=DEEP_START, symbols=deep_syms)["Close"]
    if deep_close.empty:
        return None, None
    deep_adj = ps.adjusted_close(deep_close, actions)

    last = deep_close.index[-1]
    cut = pd.Timestamp(start) if start else last - pd.DateOffset(years=RANKING_YEARS)
    recent = ps.read_wide(["High", "Low", "Volume"], prices_dir, start=str(cut.date()), symbols=symbols)
    close = deep_close.loc[deep_close.index >= cut, [c for c in symbols if c in deep_close.columns]]
    del deep_close

    def _w(col):
        return recent[col].reindex(index=close.index, columns=close.columns)

    frames = PriceFrames(
        adj_close=deep_adj.loc[deep_adj.index >= cut],
        close=close,
        high=_w("High"),
        low=_w("Low"),
        volume=_w("Volume"),
    )
    if not reaches_longest_lookback(frames.adj_close.index):
        return None, None
    last_rows = close.apply(lambda c: c.last_valid_index())
    cutoff = close.index[-(LAST_LAG + 1)] if len(close) > LAST_LAG else close.index[0]
    stale = sorted(last_rows[last_rows < cutoff].index)
    if stale:
        keep = [c for c in close.columns if c not in set(stale)]
        for name in ("adj_close", "close", "high", "low", "volume"):
            setattr(frames, name, getattr(frames, name)[keep])
        # The deep history keeps them: they were members while it ran, and
        # dropping them would add survivorship bias to the backtest.
        frames.notes.append("not ranked, no price for 5+ sessions: " + " ".join(
            f"{s} (last {last_rows[s].date()})" for s in stale))
    missing = sorted(set(symbols) - set(close.columns))
    if missing:
        frames.notes.append(f"no prices for {len(missing)}: {' '.join(missing[:20])}")
    return frames, deep_adj
