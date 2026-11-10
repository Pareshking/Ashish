"""The long history for the Backtest's History mode, from the committed store.

Paresh read a separate long NSE price file here; the US store already reaches
back to 2008, so this is a view of it with Paresh's interface:
``load()`` -> (adjusted close, None, report), ``load_value()`` -> daily traded
value in $ millions, ``average_value`` -> its trailing average.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.loaders import price_store as ps

START = "2008-01-01"


@st.cache_resource(show_spinner=False, ttl=3600, max_entries=1)
def _closes(revision: str) -> pd.DataFrame:
    close = ps.read_wide(["Close"], start=START)["Close"]
    return ps.adjusted_close(close, ps.read_actions())


def _revision() -> str:
    f = ps.files()
    return "|".join(f["years"] + f["months"] + f["days"][-1:])


def load(*_args, with_value: bool = False, **_kwargs):
    adj = _closes(_revision())
    if adj is None or adj.empty:
        return None
    report = {"built": str(adj.index[-1].date()), "last_session": str(adj.index[-1].date()),
              "source": "Yahoo Finance (data/prices), dividends reinvested"}
    return adj, (load_value() if with_value else None), report


@st.cache_resource(show_spinner=False, ttl=3600, max_entries=1)
def _value(revision: str) -> pd.DataFrame:
    w = ps.read_wide(["Close", "Volume"], start=START)
    return w["Close"] * w["Volume"] / 1e6


def load_value(*_args, **_kwargs) -> pd.DataFrame | None:
    v = _value(_revision())
    return None if v is None or v.empty else v


def average_value(value: pd.DataFrame) -> pd.DataFrame:
    """Trailing average traded value in $ millions: what liquidity.passes() reads."""
    from src.engine import liquidity

    return value.rolling(liquidity.WINDOW, min_periods=liquidity.MIN_SESSIONS).mean()
