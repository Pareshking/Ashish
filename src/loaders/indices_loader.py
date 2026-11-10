"""The S&P 1500 universe as the engine and pages read it.

``data/universe.csv`` is written by scripts/sync_universe.py from Wikipedia's
S&P 500 / 400 / 600 lists. The frame keeps Paresh's columns so every ported
page works unchanged:

  Symbol        Yahoo ticker (BRK-B), the key every price frame uses
  Company Name
  Industry      GICS sector (11). Paresh's "Industry" was NSE's ~22 macro
                industries, the unit of the sector cap; GICS sector is the US
                unit S&P itself caps and reports by.
  Indices       "SP500" / "SP400" / "SP600"
  Sub-Industry  GICS sub-industry (extra)
"""

from __future__ import annotations

import os
from typing import Any, Sequence

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UNIVERSE_FILE = os.path.join(ROOT, "data", "universe.csv")
UNIVERSE_NAME = "S&P 1500"
TAGS = {"S&P 500": "SP500", "S&P 400": "SP400", "S&P 600": "SP600"}
INDEX_NAMES = tuple(TAGS)


def _read(path: str = UNIVERSE_FILE) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Symbol", "Company Name", "Industry", "Indices", "Sub-Industry"])
    u = pd.read_csv(path, dtype=str, keep_default_na=False)
    return pd.DataFrame({
        "Symbol": u["Yahoo"],
        "Company Name": u["Company"],
        "Industry": u["Sector"],
        "Indices": u["Index"].map(TAGS).fillna(u["Index"]),
        "Sub-Industry": u["Industry"],
        "Index": u["Index"],
        "AsOf": u.get("AsOf", ""),
    })


def fetch_indices_data(selected_indices: Sequence[str] | None = None) -> pd.DataFrame:
    """The members of the named S&P indices; none named means the main book's
    index (config.MAIN_INDEX, the S&P 500)."""
    from src.core.config import MAIN_INDEX

    df = _read()
    sel = [s for s in (selected_indices or []) if s in TAGS] or [MAIN_INDEX]
    if sel:
        df = df[df["Index"].isin(sel)]
    return df.drop(columns=["Index"]).reset_index(drop=True)


def get_sync_metadata() -> dict[str, Any]:
    df = _read()
    as_of = df["AsOf"].iloc[0] if len(df) and "AsOf" in df else ""
    counts = df["Indices"].value_counts().to_dict() if len(df) else {}
    return {
        "last_synced": as_of,
        "total_stocks": int(len(df)),
        "indices": {name: {"count": int(counts.get(tag, 0)), "status": "Loaded"} for name, tag in TAGS.items()},
    }
