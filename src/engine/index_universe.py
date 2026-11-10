"""The indices a long backtest can be run on, each point in time from 2010.

Owner, 2026-10-03: a backtest from 2010 on a chosen index -- S&P 500, 100,
500, S&P 400, S&P 600, Microcap 250 or Total Market -- with size set
by the index tier (NSE builds them by free-float market cap) and an optional
traded-value floor; no market-cap cutoff.

data/membership_history.json keeps each index's own timeline under
``indices`` (nse_index_rebuild/merge_into_history.py); the top level is the
Total Market copy the live systems read. Nifty 100 is not stored: it is
S&P 500 plus Nifty Next 50 on every date, which is how NSE defines it.

An index cannot be chosen for a month before its timeline begins (Midcap and
Smallcap from Apr 2016, Microcap from Sep 2021, Total Market from Oct 2021).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.engine.membership import load_history_or_none, members_on  # noqa: F401

# key -> display name. One point-in-time timeline is recorded here, the S&P
# 1500's (data/membership_history.json, top level); per-index timelines can be
# added under "indices" (docs/TODO.md B7).
INDICES: dict[str, str] = {"sp1500": "S&P 1500"}
DEFAULT_INDEX = "sp1500"


def _stored(full: dict[str, Any], key: str) -> dict[str, Any] | None:
    sub = (full.get("indices") or {}).get(key)
    if not sub or not sub.get("baseline"):
        return None
    baseline = dict(sub["baseline"])
    # A list that starts on the 1st (2010-01-01, 2016-04-01) also answers for the
    # month-end close before it: that close signals the first month's book, and
    # NSE announces index changes about four weeks before they take effect, so
    # the list was public on the signal date.
    start = pd.Timestamp(baseline["date"])
    if start.day == 1:
        baseline["date"] = (start - pd.Timedelta(days=1)).date().isoformat()
    return {"schema_version": full.get("schema_version", 2), "index": key,
            "baseline": baseline, "changes": list(sub.get("changes") or []),
            "aliases": full.get("aliases") or {}}


def index_history(key: str, full: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """One index's membership timeline, in the form members_on() reads; None if not held."""
    full = full if full is not None else load_history_or_none()
    if not full:
        return None
    if key == DEFAULT_INDEX and full.get("baseline"):
        return {**full, "index": key, "aliases": full.get("aliases") or {}}
    return _stored(full, key)


def first_month(history: dict[str, Any] | None) -> pd.Period | None:
    """The first whole month the timeline answers for."""
    if not history or not history.get("baseline"):
        return None
    start = pd.Timestamp(history["baseline"]["date"])
    month = start.to_period("M")
    return month if start.day == 1 else month + 1   # a list from the 31st serves the next month


def ever_members(history: dict[str, Any] | None) -> set[str]:
    """Every symbol the timeline ever lists, under its current ticker too."""
    if not history or not history.get("baseline"):
        return set()
    out = set(history["baseline"]["symbols"])
    for change in history.get("changes") or []:
        out |= set(change.get("added") or [])
    aliases = history.get("aliases") or {}
    return out | {aliases[s]["new_symbol"] for s in out if s in aliases}


def all_ever_members(full: dict[str, Any] | None = None) -> set[str]:
    """Every symbol any index (and the top-level Total Market copy) ever listed."""
    full = full if full is not None else load_history_or_none()
    if not full:
        return set()
    out = ever_members(full)
    for key in (full.get("indices") or {}):
        out |= ever_members(_stored(full, key))
    return out

