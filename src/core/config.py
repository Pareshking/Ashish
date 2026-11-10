"""Central configuration for the US Momentum Terminal (S&P 1500).

Strategy parameters are Paresh's, unchanged (owner, 10 Nov 2026: "rest rules
will be same"). What is market-specific -- paths, benchmark, currency, capital,
risk-free rate, costs -- is set for the US here and nowhere else.
"""

from __future__ import annotations

import os
from typing import Final

IS_STREAMLIT_CLOUD: Final[bool] = bool(
    os.getenv("STREAMLIT_SHARING_MODE") == "enabled"
    or os.getenv("HOME", "").startswith("/home/appuser")
    or os.getenv("HOME", "").startswith("/home/adminuser")
    or os.path.exists("/mount/src")
)
BASE_DIR: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR: Final[str] = "/tmp/data_cache" if IS_STREAMLIT_CLOUD else os.path.join(BASE_DIR, "data_cache")
os.makedirs(DATA_DIR, exist_ok=True)

REPO_DATA_DIR: Final[str] = os.path.join(BASE_DIR, "data")
PRICES_DIR: Final[str] = os.path.join(REPO_DATA_DIR, "prices")
UNIVERSE_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "universe.csv")
REPO_MCAP_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "market_caps.csv")
REPO_ATH_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "all_time_highs.csv")
BENCHMARKS_FILE: Final[str] = os.path.join(REPO_DATA_DIR, "benchmarks.csv")
# Paresh's names for files that live in the repo here (startup metrics stat them).
PRICES_FILE: Final[str] = PRICES_DIR
MCAPS_FILE: Final[str] = REPO_MCAP_FILE
MCAP_PR_FILE: Final[str] = REPO_MCAP_FILE
TV_CLASSIFICATION_FILE: Final[str] = UNIVERSE_FILE

# The three S&P indices the universe is made of, and the tag each member carries
# in the Indices column (src/loaders/indices_loader.py).
INDICES_URLS: Final[dict[str, str]] = {
    "S&P 500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "S&P 400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "S&P 600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}
INDICES_LOCAL: Final[dict[str, str]] = {k: UNIVERSE_FILE for k in INDICES_URLS}
SHORT_FORMS: Final[dict[str, str]] = {"S&P 500": "SP500", "S&P 400": "SP400", "S&P 600": "SP600", "S&P 1500": ""}
# The main book's universe (owner, 10 Nov 2026: "S&P 500 becomes main book",
# after the 2020-26 point-in-time tests in docs/RESEARCH_FILTERS.md). The other
# two indices stay synced and selectable in Configuration.
MAIN_INDEX: Final[str] = "S&P 500"
UNIVERSE_NAME: Final[str] = MAIN_INDEX
# The site's name in the header, the tab title and the footer. Paresh's site
# carried its owner's name; so does this one.
SITE_NAME: Final[str] = os.getenv("SITE_NAME", "Ashish Patel")  # owner, 10 Nov 2026

HTTP_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Benchmark: the S&P 500 with dividends reinvested (SPY's dividend-adjusted
# close), the main book's own universe. Was the S&P 1500 (SPTM) until the main
# book moved to the S&P 500 (10 Nov 2026).
BENCHMARK_SYMBOL: Final[str] = "SPY_TR"
BENCHMARK_NAME: Final[str] = "S&P 500"

# ── Currency and units ───────────────────────────────────────────────────────
CURRENCY: Final[str] = "$"
# Market caps are shown in billions, traded value in millions.
CAP_UNIT: Final[float] = 1e9
CAP_UNIT_LABEL: Final[str] = "B"
VALUE_UNIT: Final[float] = 1e6
VALUE_UNIT_LABEL: Final[str] = "M"

# ── Strategy (Paresh's, unchanged) ───────────────────────────────────────────
MOMENTUM_MONTHS: Final[list[int]] = [1, 3, 6, 9, 12]
MOMENTUM_WINDOWS: Final[list[int]] = MOMENTUM_MONTHS
DEFAULT_LOOKBACK_WEIGHTS: Final[list[float]] = [0.10, 0.30, 0.30, 0.20, 0.10]
DEFAULT_SECTOR_CAP: Final[float] = 0.40
DEFAULT_STOCK_CAP: Final[float] = 0.05
DEFAULT_TARGET_VOL: Final[float] = 0.25
HIGH_52W_MIN_OBSERVATIONS: Final[int] = 126

# ── US market facts (owner, 10 Nov 2026) ─────────────────────────────────────
# Trading cost, basis points a ROUND TRIP (buy and later sell), owner: "take
# US rate". US brokers charge no commission on listed stocks; what is left is
# the bid-ask spread (about 1-3 bps for the S&P 500, 5-20 bps for the S&P
# 600), regulatory fees on sales (SEC fee and FINRA TAF, well under 1 bp) and
# market impact. 10 bps a round trip is an estimate for a $1M book, not a
# measured figure.
DEFAULT_TRANSACTION_COST_BPS: Final[float] = 10.0
# Model book (owner, 10 Nov 2026: $1M).
MODEL_BOOK_CAPITAL: Final[float] = 1_000_000.0
# Excess-return hurdle for Sharpe and Sortino: roughly the 3-month US T-bill
# yield (owner, 10 Nov 2026: 4.0%). An assumption, stated where assumptions live.
RISK_FREE_RATE: Final[float] = 0.04

# ── Published ranking (GitHub release asset, not git history) ────────────────
PRICE_SNAPSHOT_REPO: Final[str] = os.getenv("UMIYA_REPO") or "Pareshking/Ashish"
PRICE_SNAPSHOT_TAG: Final[str] = os.getenv("UMIYA_PRICE_SNAPSHOT_TAG", "data-latest")
RANKINGS_SNAPSHOT_ASSET: Final[str] = "rankings.parquet"
RANKINGS_SNAPSHOT_URL: Final[str] = os.getenv("UMIYA_RANKINGS_URL") or (
    f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
    f"{PRICE_SNAPSHOT_TAG}/{RANKINGS_SNAPSHOT_ASSET}"
)
