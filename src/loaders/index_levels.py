"""S&P index levels for size leadership: S&P 500 (large), 400 (mid), 600 (small),
against the S&P 1500 benchmark, all from data/benchmarks.csv (Yahoo's ^GSPC,
^SP400, ^SP600 price indices and SPTM, the S&P 1500 ETF).

``fetch_index_levels`` returns Paresh's long shape (date, index, close);
``benchmarks`` the wide daily frame with columns sp500, sp400, sp600, sp1500
(SPTM price) and sp1500_tr (SPTM dividend-adjusted).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.logger import logger
from src.loaders import benchmark_store

COLUMNS = {"^GSPC": "sp500", "^SP400": "sp400", "^SP600": "sp600", "SPTM": "sp1500", "SPTM_TR": "sp1500_tr"}
SIZE_KEYS = ("sp500", "sp400", "sp600")


@st.cache_data(ttl=3600, show_spinner=False)
def benchmarks() -> pd.DataFrame | None:
    try:
        df = benchmark_store.read()
    except Exception as exc:  # noqa: BLE001
        logger.warning("benchmarks.csv unreadable: %s", type(exc).__name__)
        return None
    if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None
    return df.rename(columns=COLUMNS)[[c for c in COLUMNS.values() if c in df.rename(columns=COLUMNS)]]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_levels() -> pd.DataFrame | None:
    b = benchmarks()
    if b is None:
        return None
    keys = [k for k in SIZE_KEYS if k in b]
    long = b[keys].reset_index().melt(id_vars="Date", var_name="index", value_name="close")
    return long.rename(columns={"Date": "date"}).dropna()


# Paresh's name, kept for the ported pages.
nse_benchmarks = benchmarks
