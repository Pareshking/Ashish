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
UNIVERSE_NAME: Final[str] = "S&P 1500"
# The site's name in the header, the tab title and the footer. Paresh's site
# carried its owner's name; this one's owner has not chosen yet (TODO B13).
SITE_NAME: Final[str] = os.getenv("SITE_NAME", "US Momentum Terminal")

HTTP_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Benchmark: SPDR Portfolio S&P 1500 Composite ETF, dividend-adjusted (Yahoo's
# ^SP1500 has no history). The strategy's returns are dividend-adjusted too.
BENCHMARK_SYMBOL: Final[str] = "SPTM_TR"
BENCHMARK_NAME: Final[str] = "S&P 1500"

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

# ── US market facts (owner decisions open, docs/TODO.md B11) ─────────────────
# Kept at Paresh's 30 bps a side until the owner decides: US commissions are
# ~0 and spreads on the S&P 1500 a few bps, so this is conservative.
DEFAULT_TRANSACTION_COST_BPS: Final[float] = 30.0
# Model book (owner, 10 Nov 2026: $1M).
MODEL_BOOK_CAPITAL: Final[float] = 1_000_000.0
# Excess-return hurdle for Sharpe and Sortino: roughly the 3-month US T-bill
# yield. An assumption, stated where assumptions live.
RISK_FREE_RATE: Final[float] = 0.04

# ── Published ranking (GitHub release asset, not git history) ────────────────
PRICE_SNAPSHOT_REPO: Final[str] = os.getenv("UMIYA_REPO") or "Pareshking/Ashish"
PRICE_SNAPSHOT_TAG: Final[str] = os.getenv("UMIYA_PRICE_SNAPSHOT_TAG", "data-latest")
RANKINGS_SNAPSHOT_ASSET: Final[str] = "rankings.parquet"
RANKINGS_SNAPSHOT_URL: Final[str] = os.getenv("UMIYA_RANKINGS_URL") or (
    f"https://github.com/{PRICE_SNAPSHOT_REPO}/releases/download/"
    f"{PRICE_SNAPSHOT_TAG}/{RANKINGS_SNAPSHOT_ASSET}"
)
