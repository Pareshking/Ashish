"""Prices for stocks that were in the S&P 1500 since 2020, or the S&P 500 since
2010, but are not today.

    python scripts/sync_former_members.py

The point-in-time timeline (data/membership_history.json) names every member
of every month-end. A member that has left keeps its place in the backtest
only if its prices exist; without them the pool is the survivors again. Each
former member (under its current ticker where it was renamed, ``aliases``) is
fetched from Yahoo and accepted only if the history covers the months it was
a member: Yahoo reuses tickers, and a symbol whose prices start after its
membership spell belongs to a different company now.

Writes the accepted histories into the price store (data/prices) and
data/former_members.csv: Symbol, Yahoo, FirstMember, LastMember, Status,
FirstPrice, LastPrice, Detail. Status: priced | no_data | reused_ticker |
short (covers part of the spell).
"""

from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core import market_time as mt  # noqa: E402
from src.engine import membership as mem  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402
from scripts.sync_prices import fetch, settled_only, START  # noqa: E402

OUT = os.path.join(ROOT, "data", "former_members.csv")
SLACK_DAYS = 10


def spells(history: dict) -> pd.DataFrame:
    """First and last month-end each symbol was listed."""
    dates = [history["baseline"]["date"]] + [c["date"] for c in history["changes"]]
    rows = []
    for d in dates:
        for s in mem.members_on(history, d) or set():
            rows.append((s, pd.Timestamp(d)))
    df = pd.DataFrame(rows, columns=["Symbol", "Date"])
    return df.groupby("Symbol")["Date"].agg(FirstMember="min", LastMember="max").reset_index()


def all_spells(history: dict) -> pd.DataFrame:
    """Spells on the combined timeline and on each index's own (the S&P 500's
    reaches back to Dec 2009), one row per symbol, the widest spell."""
    from src.engine import index_universe as iu
    parts = [spells(history)]
    for key in (history.get("indices") or {}):
        sub = iu.index_history(key, history)
        if sub:
            parts.append(spells(sub))
    sp = pd.concat(parts, ignore_index=True)
    return sp.groupby("Symbol").agg(FirstMember=("FirstMember", "min"), LastMember=("LastMember", "max")).reset_index()


def main() -> int:
    history = mem.load_history()
    current = set(pd.read_csv(os.path.join(ROOT, "data", "universe.csv"))["Yahoo"])
    aliases = history.get("aliases") or {}
    sp = all_spells(history)
    former = sp[~sp["Symbol"].isin(current)].copy()
    former["Yahoo"] = former["Symbol"].map(lambda s: aliases.get(s, {}).get("new_symbol", s))
    # Every symbol with any history (a member delisted in 2015 has none in 2026).
    stored = set(ps.read_columns([])["Symbol"].astype(str).unique())
    todo = sorted(set(former["Yahoo"]) - stored - current)
    print(f"{len(former)} former members (S&P 1500 since {history['baseline']['date']}, S&P 500 since its first list); "
          f"{len(former) - len(todo)} already priced or renamed into today's list; fetching {len(todo)}")
    target = mt.last_downloadable_session()
    prices, actions = fetch(todo, START) if todo else (ps.normalise(None), pd.DataFrame(columns=ps.ACTION_COLS))
    prices = settled_only(prices, target)
    got = prices.groupby("Symbol")["Date"].agg(["min", "max"]) if len(prices) else pd.DataFrame(columns=["min", "max"])

    status, first, last, detail = [], [], [], []
    keep = set()
    for r in former.itertuples(index=False):
        y = r.Yahoo
        if y in current:
            status.append("renamed_member"); first.append(""); last.append(""); detail.append("in today's list")
            continue
        if y not in got.index:
            ok_stored = y in stored
            status.append("priced" if ok_stored else "no_data"); first.append(""); last.append("")
            detail.append("already in the store" if ok_stored else "Yahoo returns nothing")
            continue
        a, b = got.loc[y, "min"], got.loc[y, "max"]
        first.append(str(a.date())); last.append(str(b.date()))
        if a > r.FirstMember + pd.Timedelta(days=SLACK_DAYS):
            status.append("reused_ticker"); detail.append(f"prices start {a.date()}, membership {r.FirstMember.date()}")
        elif b < r.LastMember - pd.Timedelta(days=SLACK_DAYS):
            status.append("short"); detail.append(f"prices end {b.date()}, membership to {r.LastMember.date()}")
            keep.add(y)
        else:
            status.append("priced"); detail.append(""); keep.add(y)
    former["Status"], former["FirstPrice"], former["LastPrice"], former["Detail"] = status, first, last, detail
    # A row already priced keeps what the earlier run recorded (its source:
    # Stonks/tickers rows are not Yahoo's).
    if os.path.exists(OUT):
        before = pd.read_csv(OUT, dtype=str, keep_default_na=False).set_index("Symbol")
        cols = [c for c in ("Status", "FirstPrice", "LastPrice", "Detail", "Source") if c in before]
        for i, r in former.iterrows():
            if r["Detail"] == "already in the store" and r["Symbol"] in before.index:
                for c in cols:
                    former.loc[i, c] = before.loc[r["Symbol"], c]
    accepted = prices[prices["Symbol"].isin(keep)]
    written = ps.store(accepted, mt.ny_today())
    acts = pd.concat([ps.read_actions(), actions[actions["Symbol"].isin(keep)]], ignore_index=True)
    ps.write_actions(acts)
    former.sort_values("Symbol").to_csv(OUT, index=False, date_format="%Y-%m-%d")
    print(former["Status"].value_counts().to_string())
    print(f"{accepted['Symbol'].nunique()} former members' prices written into {len(written)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
