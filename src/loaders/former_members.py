"""Stocks that have left the S&P 1500, for the point-in-time backtest.

The price store keeps every symbol it ever synced, so a member that leaves
keeps its history in ``data/prices`` up to its last session; nothing extra is
fetched here. Its GICS sector is kept in ``data/sector_history.csv`` (written
by scripts/sync_universe.py: every symbol ever on the list, with the sector it
last carried), so the sector cap can still place it.

What cannot be recovered: members that left BEFORE the first snapshot
(10 Nov 2026) and whose tickers Yahoo no longer serves. See
docs/DATA_CORRECTNESS.md (survivorship).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pandas as pd

REPO_DATA = Path(__file__).resolve().parents[2] / "data"
INDEX_FILE = REPO_DATA / "universe_index.csv"
UNIVERSE_FILE = REPO_DATA / "universe.csv"
SECTOR_HISTORY_FILE = REPO_DATA / "sector_history.csv"


MONTHLY_FILE = REPO_DATA / "membership_monthly.csv"


def _sectors() -> dict[str, str]:
    """GICS sector per symbol: the point-in-time month-end lists (the sector a
    member last carried while listed), then the sector history, then today's list."""
    out: dict[str, str] = {}
    if MONTHLY_FILE.exists():
        m = pd.read_csv(MONTHLY_FILE, dtype=str, keep_default_na=False).sort_values("Date")
        m = m[m["Sector"].str.strip() != ""]
        aliases = {}
        try:
            import json
            aliases = json.loads((REPO_DATA / "membership_history.json").read_text()).get("aliases") or {}
        except (OSError, ValueError):
            pass
        for sym, sec in zip(m["Yahoo"], m["Sector"]):
            out[sym] = sec
            if sym in aliases:
                out.setdefault(aliases[sym]["new_symbol"], sec)
    if SECTOR_HISTORY_FILE.exists():
        h = pd.read_csv(SECTOR_HISTORY_FILE, dtype=str, keep_default_na=False)
        out.update(dict(zip(h["Symbol"], h["Sector"])))
    if UNIVERSE_FILE.exists():
        u = pd.read_csv(UNIVERSE_FILE, dtype=str, keep_default_na=False)
        out.update(dict(zip(u["Yahoo"], u["Sector"])))
    return out


def index_frame() -> pd.DataFrame:
    """Symbol and Industry (GICS sector) for every symbol ever on the list."""
    s = _sectors()
    return pd.DataFrame({"Symbol": list(s), "Industry": list(s.values())})


def symbols_needed(history: dict[str, Any] | None, columns: Iterable[str]) -> list[str]:
    from src.engine.membership import members_on

    if not history or not history.get("baseline"):
        return []
    have = set(columns)
    ever = set(history["baseline"]["symbols"])
    for c in history.get("changes") or []:
        ever |= set(c.get("added") or [])
    _ = members_on  # same module Paresh used; kept for parity
    return sorted(ever - have)


def load() -> pd.DataFrame:
    return pd.DataFrame()


def unavailable() -> list[str]:
    return []


def with_former_members(adj_close: pd.DataFrame, history: dict[str, Any] | None = None,
                        prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """The deep frame already carries every symbol the store has synced."""
    return adj_close


def industry_for(symbols: Iterable[str], **_ignored) -> dict[str, str]:
    """GICS sector of each symbol; "Other" for one never seen on the list."""
    s = _sectors()
    return {sym: s.get(sym, "Other") for sym in symbols}
