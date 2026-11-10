"""Benchmark history and the market regime (benchmark against its 200-day EMA)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.config import BENCHMARK_SYMBOL
from src.core.logger import logger
from src.core.types import MarketRegime, RegimeData


def fetch_benchmark_history(period: str = "2y", symbol: str = BENCHMARK_SYMBOL) -> pd.Series:
    """A benchmark series from data/benchmarks.csv; empty on any failure."""
    from src.loaders import benchmark_store

    try:
        return benchmark_store.history(period=period, symbol=symbol)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to read benchmark {symbol}: {e}")
        return pd.Series(dtype=float, name=symbol)


@st.cache_data(show_spinner=False, ttl=3600)
def get_market_regime(benchmark_symbol: str = BENCHMARK_SYMBOL) -> RegimeData:
    """Benchmark close against its 200-day EMA, over the whole series."""
    try:
        close_s = pd.to_numeric(fetch_benchmark_history(period="max", symbol=benchmark_symbol),
                                errors="coerce").dropna()
        if close_s.empty:
            return RegimeData(MarketRegime.UNKNOWN, 0.0, 0.0, 0.0)
        price = float(close_s.iloc[-1])
        dma = float(close_s.ewm(span=200, min_periods=160).mean().iloc[-1])
        dist = ((price - dma) / dma * 100) if dma > 0 else 0.0
        status = MarketRegime.BULLISH if price >= dma else MarketRegime.BEARISH
        return RegimeData(status, price, dma, dist)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to compute market regime: {e}")
        return RegimeData(MarketRegime.UNKNOWN, 0.0, 0.0, 0.0)
