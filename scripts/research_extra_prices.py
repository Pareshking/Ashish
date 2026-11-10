"""Research-only prices for former S&P 500 members the store cannot price,
from a local copy of github:Johnbrick123/sp500-data's prices.parquet.

    python scripts/research_extra_prices.py --source PATH/prices.parquet --out PATH.parquet

The dataset has no licence file and carries Tiingo, Quandl WIKI and CRSP
rows. Owner, 10 Nov 2026: first research only; then commit it all, with the
repository made private (scripts/import_former_members_jb.py writes the store;
this script writes a file outside data/).

For each symbol on the point-in-time S&P 500 timeline whose membership spell
has no price in the store (under its own ticker or, renamed, today's), the
dataset's ticker for the same company is taken: the exact name for a dated
symbol from data/reused_tickers.csv (LSI-201405), else a ticker with the same
base whose history covers the spell (the dataset suffixes dead companies'
tickers with -YYYYMM). Rows are written in the store's long form with Close
the dataset's adj_close (split and dividend adjusted, total return: no
dividend rows to add) and High/Low scaled by the same factor.

The dataset was checked against our own prices on 10 Nov 2026
(docs/DATA_CORRECTNESS.md): 643 of 649 former members agree over their spells,
cash takeovers end at the offer.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
import pyarrow.parquet as pq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.engine import index_universe as iu  # noqa: E402
from src.engine import membership as mem  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402
from scripts.sync_former_members import spells  # noqa: E402

SLACK_START = pd.Timedelta(days=10)
SLACK_END = pd.Timedelta(days=40)


TAIL = pd.Timedelta(days=45)   # rows kept after the last month-end as a member (the audit's window)


def select(source: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Rows for every S&P 500 symbol whose spell the store cannot price.
    Returns (long rows, one row per symbol found: Symbol, Ticker, Source,
    FirstMember, LastMember, FirstPrice, LastPrice), still-missing symbols)."""
    full = mem.load_history()
    aliases = full.get("aliases") or {}
    sp = spells(iu.index_history("sp500", full))
    sp["Stored"] = sp["Symbol"].map(lambda s: aliases.get(s, {}).get("new_symbol", s))
    have = ps.read_columns([], symbols=set(sp["Symbol"]) | set(sp["Stored"]))
    rng = have.groupby("Symbol", observed=True)["Date"].agg(["min", "max"])

    def priced(r) -> bool:
        for s in (r.Symbol, r.Stored):
            if s in rng.index and rng.loc[s, "min"] <= r.LastMember and rng.loc[s, "max"] >= r.FirstMember:
                return True
        return False

    todo = sp[[not priced(r) for r in sp.itertuples()]]
    t = pq.read_table(source, columns=["date", "ticker", "high", "low", "close", "adj_close",
                                       "volume", "source"]).to_pandas()
    t = t[t["date"] >= "2008-01-01"]
    t["base"] = t["ticker"].str.replace(r"-\d{6}$", "", regex=True)
    span = t.groupby("ticker")["date"].agg(["min", "max"])
    parts, found, missing = [], [], []
    for r in todo.itertuples():
        cands = [r.Symbol] if r.Symbol in span.index and "-" in r.Symbol[-7:] else \
            sorted(set(t.loc[t["base"] == r.Symbol, "ticker"]))
        ok = [c for c in cands if span.loc[c, "min"] <= max(r.FirstMember, pd.Timestamp("2008-01-02")) + SLACK_START
              and span.loc[c, "max"] >= r.LastMember - SLACK_END]
        if not ok:
            missing.append(r.Symbol)
            continue
        d = t[(t["ticker"] == ok[0]) & (t["date"] <= r.LastMember + TAIL)]
        f = d["adj_close"] / d["close"]
        parts.append(pd.DataFrame({"Date": d["date"], "Symbol": r.Symbol, "High": d["high"] * f,
                                   "Low": d["low"] * f, "Close": d["adj_close"], "Volume": d["volume"].fillna(0)}))
        found.append({"Symbol": r.Symbol, "Ticker": ok[0],
                      "Source": " ".join(f"{k} {v:.0%}" for k, v in d["source"].value_counts(normalize=True).items()),
                      "FirstMember": r.FirstMember, "LastMember": r.LastMember,
                      "FirstPrice": d["date"].min(), "LastPrice": d["date"].max()})
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=ps.COLUMNS)
    print(f"{len(todo)} S&P 500 symbols unpriced in the store; {len(found)} found in the dataset; "
          f"{len(missing)} still missing: {' '.join(missing)}")
    return out, pd.DataFrame(found), missing


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if os.path.abspath(args.out).startswith(os.path.join(ROOT, "data") + os.sep):
        raise SystemExit("this writes a research file; scripts/import_former_members_jb.py writes the store")
    out, _, _ = select(args.source)
    out.to_parquet(args.out, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
