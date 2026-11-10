"""Prices for former S&P 1500 members that Yahoo no longer serves, from the
public GitHub dataset Stonks/tickers (per-ticker daily CSVs by exchange).

What the dataset is, checked 10 Nov 2026 against our own Yahoo store on 30
current members: a snapshot of Yahoo's ADJUSTED daily prices (split and
dividend) taken on 10 Oct 2023. Non-dividend payers equal our closes exactly
(META, LSCC, PENN, IPGP, ACAD ... ratio 1.0000); dividend payers sit below by
their cumulative dividend factor (IBM 0.81, GS 0.90). Every file ends on
2023-10-10. So the closes are TOTAL-RETURN closes, stored here as Close with no
dividend rows (the same returns as our split-adjusted close plus dividends),
and a member delisted after Oct 2023 is covered only to that date.

Accepted per symbol only when the file starts on or before the symbol's first
month-end as a member (a later start is a reused ticker) and the symbol has no
Yahoo history in the store. Volume is in millions of shares in the dataset;
about a third of the files have none (stored as 0).
Updates data/former_members.csv (Status, Source).
"""

from __future__ import annotations

import io
import os
import sys
import concurrent.futures as cf

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core import market_time as mt  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402

RAW = "https://raw.githubusercontent.com/Stonks/tickers/HEAD/tickers/{ex}/{sym}.csv"
EXCHANGES = ("nyse", "nasdaq", "amex")
FORMER = os.path.join(ROOT, "data", "former_members.csv")
SNAPSHOT_END = pd.Timestamp("2023-10-10")
SLACK = pd.Timedelta(days=10)


def fetch(sym: str, s: requests.Session) -> pd.DataFrame | None:
    for ex in EXCHANGES:
        r = s.get(RAW.format(ex=ex, sym=sym.replace("-", ".")), timeout=30)
        if r.status_code == 200 and r.text.startswith("DATE"):
            d = pd.read_csv(io.StringIO(r.text), parse_dates=["DATE"])
            d["Exchange"] = ex
            return d
    return None


def main() -> int:
    f = pd.read_csv(FORMER, parse_dates=["FirstMember", "LastMember"], dtype={"FirstPrice": str, "LastPrice": str})
    if "Source" not in f:
        f["Source"] = f["Status"].map({"priced": "yahoo", "renamed_member": "yahoo (today's ticker)"}).fillna("")
    todo = f[f["Status"].isin(["no_data", "reused_ticker"])]
    s = requests.Session()
    with cf.ThreadPoolExecutor(8) as pool:
        got = dict(zip(todo["Symbol"], pool.map(lambda x: fetch(x, s), todo["Symbol"])))
    parts = []
    for i, r in todo.iterrows():
        d = got.get(r["Symbol"])
        if d is None or d.empty:
            f.loc[i, ["Status", "Detail"]] = ["no_data", "neither Yahoo nor Stonks/tickers"]
            continue
        lo, hi = d["DATE"].min(), d["DATE"].max()
        if lo > r["FirstMember"] + SLACK:
            f.loc[i, ["Status", "Detail"]] = ["reused_ticker", f"Stonks/tickers starts {lo.date()} too: another company"]
            continue
        d = d[d["DATE"] >= pd.Timestamp("2008-01-01")]
        parts.append(pd.DataFrame({"Date": d["DATE"], "Symbol": r["Symbol"], "High": d["HIGH"], "Low": d["LOW"],
                                   "Close": d["CLOSE"],
                                   # 123 of the files have no volume column: stored as 0 (volume
                                   # feeds only the optional liquidity floor and the spike flag).
                                   "Volume": ((d["VOLUME"].fillna(0) * 1e6).round() if "VOLUME" in d else 0)}))
        full = hi >= r["LastMember"] - SLACK
        f.loc[i, ["Status", "Source", "FirstPrice", "LastPrice", "Detail"]] = [
            "priced" if full else "short", "github:Stonks/tickers (Yahoo adjusted, snapshot 2023-10-10)",
            str(lo.date()), str(hi.date()),
            "" if full else f"covered to {hi.date()}, member to {r['LastMember'].date()}"]
    if parts:
        long = pd.concat(parts, ignore_index=True)
        long = long[long["Date"].map(lambda x: mt.is_session(x.date()))]
        written = ps.store(long, mt.ny_today())
        print(f"{long['Symbol'].nunique()} symbols, {len(long):,} rows into {len(written)} files")
    f.sort_values("Symbol").to_csv(FORMER, index=False, date_format="%Y-%m-%d")
    print(f.groupby(["Status", "Source"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
