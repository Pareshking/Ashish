"""Market caps in dollars, from data/market_caps.csv (scripts/sync_market_caps.py)."""

from __future__ import annotations

import os
from typing import Sequence

import pandas as pd

from src.core.config import REPO_MCAP_FILE


def fetch_market_caps(symbols: Sequence[str], force_refresh: bool = False) -> pd.Series:
    if not os.path.exists(REPO_MCAP_FILE):
        return pd.Series(dtype=float)
    df = pd.read_csv(REPO_MCAP_FILE, dtype={"Symbol": str})
    s = pd.Series(pd.to_numeric(df["MarketCap"], errors="coerce").values, index=df["Symbol"])
    return s.reindex(list(symbols))
