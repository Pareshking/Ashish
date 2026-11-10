"""The S&P 500's point-in-time month-end lists from the public GitHub dataset
fja05680/sp500, checked against our Wikipedia revisions.

    python scripts/import_sp500_history.py [--start 2009-12] [--csv PATH]

Why (10 Nov 2026). Our S&P 500 timeline was read from Wikipedia's page as it
stood at each month-end. Compared with fja05680/sp500 over Dec 2019 - Aug 2026
the two agree on 99.97% of member-months, and where they differ the S&P Dow
Jones press releases side with the dataset: Etsy, Teradyne and Catalent joined
before the open on 21 Sep 2020 (press.spglobal.com, 4 Sep 2020), CRH, Carvana
and Comfort Systems on 22 Dec 2025 (press.spglobal.com, 5 Dec 2025), yet the
Wikipedia revision at those month-ends still listed the stocks they replaced.
The page is edited by hand and sometimes late; a month-end snapshot inherits
the delay.

What the dataset is: Andreas Clenow's list from "Trading Evolved" for
1996-2019, then maintained from S&P announcements by its author (README,
fetched 10 Nov 2026). For 2010-2019 that is a source independent of Wikipedia.
Tickers are as traded on the day (FB in 2015, META in 2023): today's ticker for
an old one comes from our aliases (CIK and company name from the Wikipedia
revisions, scripts/build_membership_history.py).

Rule: each month-end from --start up to the dataset's last date is the
dataset's list on that date; after it, our Wikipedia/nightly snapshots. Every
month-end where the two disagree is written to docs/data_checks/sp500_source_check.csv
so a difference is visible, not silently resolved. Only ``indices.sp500`` in
data/membership_history.json is replaced; the combined S&P 1500 timeline (a
research universe) is left as built.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.engine import index_universe as iu  # noqa: E402
from src.engine import membership as mem  # noqa: E402

URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
       "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
REPORT = os.path.join(ROOT, "docs", "data_checks", "sp500_source_check.csv")
# A ticker that named another company before a date (data/reused_tickers.csv,
# each row with its evidence): month-ends up to Until list it as StoredAs.
REUSED = os.path.join(ROOT, "data", "reused_tickers.csv")


def reused() -> pd.DataFrame:
    if not os.path.exists(REUSED):
        return pd.DataFrame(columns=["Symbol", "Until", "StoredAs"])
    return pd.read_csv(REUSED, parse_dates=["Until"])


def epoch(symbols: list[str], when: pd.Timestamp, table: pd.DataFrame) -> list[str]:
    swap = {r.Symbol: r.StoredAs for r in table.itertuples() if when <= r.Until}
    return sorted(swap.get(s, s) for s in symbols)


def to_yahoo(t: str) -> str:
    return t.strip().upper().replace(".", "-")


def read_dataset(path: str | None) -> tuple[pd.Series, str]:
    raw = open(path, "rb").read() if path else requests.get(URL, timeout=60).content
    df = pd.read_csv(io.BytesIO(raw), parse_dates=["date"]).sort_values("date")
    lists = df.set_index("date")["tickers"].map(lambda s: sorted({to_yahoo(t) for t in s.split(",") if t.strip()}))
    return lists, hashlib.sha256(raw).hexdigest()


def on(lists: pd.Series, when: pd.Timestamp) -> list[str]:
    return lists[lists.index <= when].iloc[-1]


def build(lists: pd.Series, ours: dict, start: str, today: pd.Timestamp) -> tuple[dict, pd.DataFrame]:
    last = lists.index.max()
    month_ends = pd.date_range(pd.Period(start, "M").end_time.normalize(), today, freq="ME")
    sub = mem.empty_history("S&P 500")
    table = reused()
    report = []
    for me in month_ends:
        wiki = mem.members_on(ours, me) if pd.Timestamp(ours["baseline"]["date"]) <= me else None
        if me <= last:
            syms = on(lists, me)
            if wiki is not None and set(syms) != set(wiki):
                report.append({"Date": me.date(), "DatasetOnly": " ".join(sorted(set(syms) - set(wiki))),
                               "WikipediaOnly": " ".join(sorted(set(wiki) - set(syms))), "Used": "dataset"})
        else:
            syms = sorted(wiki or [])
        sub, _ = mem.record_snapshot(sub, me.date(), epoch(syms, me, table))
    # After the last month-end: the nightly snapshots already recorded.
    for c in ours.get("changes") or []:
        d = pd.Timestamp(c["date"])
        if d > month_ends[-1]:
            sub, _ = mem.record_snapshot(sub, d.date(), mem.members_on(ours, d))
    return sub, pd.DataFrame(report, columns=["Date", "DatasetOnly", "WikipediaOnly", "Used"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default="2009-12")
    ap.add_argument("--csv", help="a local copy of the dataset file (default: download)")
    args = ap.parse_args(argv)
    full = mem.load_history()
    ours = iu.index_history("sp500", full)
    lists, sha = read_dataset(args.csv)
    today = pd.Timestamp(mem.coverage(ours)[1])
    sub, report = build(lists, ours, args.start, today)
    full.setdefault("indices", {})["sp500"] = {"baseline": sub["baseline"], "changes": sub["changes"]}
    full["sp500_source"] = (f"github:fja05680/sp500 month-end lists {args.start} .. {lists.index.max().date()} "
                            f"(file sha256 {sha[:12]}); Wikipedia revisions and nightly snapshots after; "
                            "disagreements in docs/data_checks/sp500_source_check.csv")
    mem.save_history(full, mem.HISTORY_PATH)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    report.to_csv(REPORT, index=False)
    ever = set(sub["baseline"]["symbols"]).union(*[set(c["added"]) for c in sub["changes"]])
    print(f"S&P 500 {sub['baseline']['date']} .. {today.date()}: {len(sub['changes'])} change dates, "
          f"{len(ever)} symbols ever; {len(report)} month-ends where Wikipedia disagreed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
