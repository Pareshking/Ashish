"""Prices for former S&P 500 members the store cannot price, from a local
copy of github:Johnbrick123/sp500-data's prices.parquet, into the store.

    python scripts/import_former_members_jb.py --source PATH/prices.parquet

Owner, 10 Nov 2026: commit all of it, with the repository private (the
dataset has no licence file and carries Tiingo, Quandl WIKI and CRSP rows).

Selection is scripts/research_extra_prices.select: the dataset's ticker for
the same company whose history covers the membership spell; rows from 2008 to
45 days after the last month-end as a member. Close is the dataset's adj_close
(split and dividend adjusted, total return), as for the Stonks/tickers rows,
so no dividend rows are added. Each symbol's row in data/former_members.csv
records the dataset and its sources' shares (e.g. "tiingo 99%").

Checked against our own prices on 10 Nov 2026 (docs/DATA_CORRECTNESS.md):
643 of 649 former members agree over their spells (the 6 were our errors);
cash takeovers end at the offer.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core import market_time as mt  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402
from scripts.research_extra_prices import select  # noqa: E402

FORMER = os.path.join(ROOT, "data", "former_members.csv")
LABEL = "github:Johnbrick123/sp500-data"


def extend_short(source: str) -> tuple[pd.DataFrame, list[str]]:
    """S&P 500 former members whose stored prices end before their last
    month-end as a member (the Stonks/tickers rows end at its 10 Oct 2023
    snapshot: EA and AVB were members to Jul 2026). The dataset's later rows
    are spliced on, scaled so its total-return close equals the store's on the
    store's last day (the two are adjusted as of different dates)."""
    import pyarrow.parquet as pq
    from src.engine import index_universe as iu
    from src.engine import membership as mem
    from scripts.sync_former_members import spells
    sp = spells(iu.index_history("sp500", mem.load_history())).set_index("Symbol")
    have = ps.read_columns(["Close"], symbols=set(sp.index))
    last = have.sort_values("Date").groupby("Symbol", observed=True).tail(1).set_index("Symbol")
    short = [s for s in last.index if s in sp.index
             and last.loc[s, "Date"] < sp.loc[s, "LastMember"] - pd.Timedelta(days=10)]
    t = pq.read_table(source, columns=["date", "ticker", "high", "low", "close", "adj_close", "volume"]).to_pandas()
    t = t[t["ticker"].isin(short)]
    parts, done = [], []
    for s in short:
        d = t[t["ticker"] == s].set_index("date").sort_index()
        a = last.loc[s, "Date"]
        if a not in d.index or d.loc[a:].shape[0] < 2:
            continue
        k = float(last.loc[s, "Close"]) / float(d.loc[a, "adj_close"])
        d = d.loc[a:].iloc[1:]
        d = d[d.index <= sp.loc[s, "LastMember"] + TAIL]
        f = d["adj_close"] / d["close"] * k
        parts.append(pd.DataFrame({"Date": d.index, "Symbol": s, "High": d["high"].values * f.values,
                                   "Low": d["low"].values * f.values, "Close": d["adj_close"].values * k,
                                   "Volume": d["volume"].fillna(0).values}))
        done.append(s)
    return (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=ps.COLUMNS)), done


TAIL = pd.Timedelta(days=45)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    args = ap.parse_args(argv)
    rows, found, missing = select(args.source)
    ext, extended = extend_short(args.source)
    if len(ext):
        ext = ext[ext["Date"].map(lambda x: mt.is_session(x.date()))]
        ps.store(ext, mt.ny_today())
        f = pd.read_csv(FORMER, dtype=str, keep_default_na=False)
        m = f["Symbol"].isin(extended)
        f.loc[m, "Source"] = f.loc[m, "Source"] + "; extended from " + LABEL
        f.loc[m, "Status"] = "priced"
        f.loc[m, "Detail"] = "after the snapshot: " + LABEL + ", scaled to the stored close"
        f.to_csv(FORMER, index=False)
        print(f"extended {len(extended)} short S&P 500 former members: {' '.join(extended)}")
    if rows.empty:
        return 0
    rows = rows[rows["Date"].map(lambda x: mt.is_session(x.date()))]
    written = ps.store(rows, mt.ny_today())
    f = pd.read_csv(FORMER, dtype=str, keep_default_na=False)
    f = f[~f["Symbol"].isin(found["Symbol"])]
    add = pd.DataFrame({
        "Symbol": found["Symbol"], "FirstMember": found["FirstMember"].dt.date.astype(str),
        "LastMember": found["LastMember"].dt.date.astype(str), "Yahoo": found["Symbol"],
        "Status": "priced", "FirstPrice": found["FirstPrice"].dt.date.astype(str),
        "LastPrice": found["LastPrice"].dt.date.astype(str),
        "Detail": "dataset ticker " + found["Ticker"],
        "Source": LABEL + " (" + found["Source"] + ")"})
    f = pd.concat([f, add], ignore_index=True).sort_values("Symbol")
    f.to_csv(FORMER, index=False)
    print(f"{rows['Symbol'].nunique()} symbols, {len(rows):,} rows into {len(written)} files; "
          f"{len(missing)} still missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
