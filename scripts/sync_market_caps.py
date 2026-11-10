"""Market capitalisation for the S&P 1500.

Nasdaq.com's screener serves every US-listed stock's market cap and last sale
in one request. The share count is taken as marketCap / lastsale (both from the
same Nasdaq row) and valued at OUR latest stored close, so the cap is dated to
the same session as the ranking. A member Nasdaq leaves blank (Brown-Forman B,
10 Nov 2026) is asked of Yahoo (``fast_info``: shares outstanding).

Writes ``data/market_caps.csv``: Symbol, Shares, Close, MarketCap, AsOf, Source.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.loaders import price_store as ps  # noqa: E402

URL = "https://api.nasdaq.com/api/screener/stocks"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36", "Accept": "application/json"}
OUT = os.path.join(ROOT, "data", "market_caps.csv")
UNIVERSE = os.path.join(ROOT, "data", "universe.csv")


def nasdaq_shares() -> pd.Series:
    r = requests.get(URL, params={"tableonly": "true", "download": "true"}, headers=HEADERS, timeout=120)
    r.raise_for_status()
    rows = r.json()["data"]["rows"]
    df = pd.DataFrame(rows)
    df["Yahoo"] = df["symbol"].str.strip().str.upper().str.replace("/", "-", regex=False)
    cap = pd.to_numeric(df["marketCap"], errors="coerce")
    last = pd.to_numeric(df["lastsale"].str.replace(r"[$,]", "", regex=True), errors="coerce")
    shares = (cap / last).where((cap > 0) & (last > 0))
    return pd.Series(shares.values, index=df["Yahoo"]).dropna()


def yahoo_shares(symbols: list[str]) -> pd.Series:
    import yfinance as yf

    out = {}
    for s in symbols:
        try:
            v = yf.Ticker(s).fast_info.get("shares")
            if v:
                out[s] = float(v)
        except Exception:  # noqa: BLE001 - one missing cap is reported, not fatal
            pass
    return pd.Series(out, dtype=float)


def main() -> int:
    syms = pd.read_csv(UNIVERSE)["Yahoo"].tolist()
    recent = ps.read_long(start=str(pd.Timestamp.today() - pd.Timedelta(days=20)))
    last = recent.sort_values("Date").groupby("Symbol").tail(1).set_index("Symbol")
    shares = nasdaq_shares().reindex(syms)
    src = pd.Series("nasdaq", index=syms).where(shares.notna(), "")
    missing = shares[shares.isna()].index.tolist()
    if missing:
        y = yahoo_shares(missing)
        shares.loc[y.index] = y
        src.loc[y.index] = "yahoo"
    df = pd.DataFrame({"Symbol": syms, "Shares": shares.values, "Source": src.values})
    df["Close"] = df["Symbol"].map(last["Close"]).astype(float)
    df["AsOf"] = df["Symbol"].map(last["Date"]).dt.strftime("%Y-%m-%d")
    df["MarketCap"] = (df["Shares"] * df["Close"]).round(0)
    df = df[["Symbol", "Shares", "Close", "MarketCap", "AsOf", "Source"]]
    df.to_csv(OUT, index=False, float_format="%.10g")
    gone = df[df["MarketCap"].isna()]["Symbol"].tolist()
    print(f"market caps: {df['MarketCap'].notna().sum()}/{len(df)} "
          f"(nasdaq {int((df['Source'] == 'nasdaq').sum())}, yahoo {int((df['Source'] == 'yahoo').sum())}); "
          f"none for: {' '.join(gone) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
