"""Paresh read TradingView sectors for stocks outside NSE's indices. Every US
member carries its GICS sector in data/universe.csv, so there is nothing to add."""

from __future__ import annotations


def load_tv_classification() -> dict[str, dict[str, str]]:
    return {}
