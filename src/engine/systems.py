"""Per-system facts the strategy runs on: ledger, inception and membership.

One system in the US terminal, the S&P 500 (owner, 10 Nov 2026), whose
point-in-time membership is ``data/membership_history.json`` (built from
dated snapshots of the S&P 500, 400 and 600 lists by scripts/sync_universe.py).
The functions keep Paresh's per-system signatures so the ported pages work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.engine.extra_universe import SYSTEM_750
from src.engine.track_record import INCEPTION, LEDGER_PATH

DATA = Path(__file__).resolve().parents[2] / "data"
LEDGERS = {SYSTEM_750: LEDGER_PATH}


def ledger_path(system: str) -> Path:
    return LEDGERS.get(system, LEDGER_PATH)


def inception(system: str) -> pd.Period:
    """The first month a system's live record may hold."""
    return INCEPTION


def membership_for(system: str) -> dict[str, Any] | None:
    """The point-in-time timeline the record and backtest score on: the main
    book's index (config.MAIN_INDEX, the S&P 500)."""
    from src.engine import index_universe as iu

    return iu.index_history(iu.DEFAULT_INDEX)


# Backtest reporting starts at each system's canonical live inception.
# Price history before these months remains available for signal formation
# (12-month momentum + EMA warm-up), but it is never presented as portfolio
# ownership or performance history.
BACKTEST_START: dict[str, str] = {}


def backtest_months(system: str, last_session) -> int | None:
    """Completed months a system's backtest may report as of `last_session`.

    None for the 750 (its own default applies); 0 while the first month is
    still running.
    """
    if system not in BACKTEST_START:
        return None
    last_completed = pd.Timestamp(last_session).to_period("M") - 1
    return max(0, (last_completed - pd.Period(BACKTEST_START[system], freq="M")).n + 1)
