"""Corporate actions for US prices.

Paresh had to find and neutralise splits, bonuses and demergers that its
sources had not adjusted. Yahoo's US daily bars arrive split-adjusted, and
dividend adjustment is computed from Yahoo's own dividend record
(``src/loaders/price_store.adjusted_close``). What is left for this module is
the read-time hook the engine already calls: a list of flagged sessions
(``data/corporate_actions_log.json``, normally empty) that ``scripts/audit_prices.py``
found and a person confirmed against an independent source.

The functions keep Paresh's signatures so the ported engine runs unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "corporate_actions_log.json"


def load_events(path: str | Path = LOG_PATH, fo_symbols: set[str] | None = None) -> list[dict[str, Any]]:
    """Confirmed unadjusted actions, as {"symbol", "date", "ratio"} dicts."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text())
    except Exception:  # noqa: BLE001 - an unreadable log is no events, logged by the audit
        return []
    events = raw.get("events", raw) if isinstance(raw, dict) else raw
    return [e for e in events if e.get("symbol") and e.get("date") and float(e.get("ratio") or 0) > 0]


def adjust_prices(prices: pd.DataFrame, events: list[dict[str, Any]] | None
                  ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Scale each flagged symbol's history before its event date by 1/ratio."""
    if prices is None or not events:
        return prices, []
    out = prices.copy()
    applied = []
    for e in events:
        sym, d, ratio = e["symbol"], pd.Timestamp(e["date"]), float(e["ratio"])
        if sym not in out.columns:
            continue
        mask = out.index < d
        if not mask.any():
            continue
        out.loc[mask, sym] = out.loc[mask, sym] / ratio
        applied.append({"symbol": sym, "date": str(d.date()), "ratio": ratio})
    return out, applied


def adjust_ohlc(frames: dict[str, pd.DataFrame], events: list[dict[str, Any]] | None
                ) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """``adjust_prices`` on every price frame at once (volume is not touched)."""
    if not events:
        return frames, []
    out, applied = {}, []
    for k, f in frames.items():
        out[k], a = adjust_prices(f, events)
        applied = applied or a
    return out, applied


def trustworthy_ath(highs: pd.Series, peak_dates: pd.Series | None,
                    events: list[dict[str, Any]] | None) -> pd.Series:
    """All-time highs are computed from the same split-adjusted store as every
    other price here, so there is no second price scale to distrust."""
    return highs
