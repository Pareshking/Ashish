"""Rebuild the point-in-time S&P 1500 membership from Wikipedia's page history.

    python scripts/build_membership_history.py [--start 2019-12]

Wikipedia keeps every revision of the S&P 500, 400 and 600 constituent lists,
each timestamped. For every month-end from --start the LAST revision saved on
or before that day is read, so each month-end list is what the page said at
that close -- an editor-maintained copy of S&P's announcements, usually within
days of the effective date. The month-end is what the strategy needs: it
signals on the last session of each month.

Writes data/membership_history.json (baseline at the first month-end, then a
change per month-end where the list moved, then today's snapshot), with
``aliases`` for tickers that changed (an old symbol whose company carries a
different symbol later, matched on the company name), and
data/membership_monthly.csv (Date, Index, Symbol) for audits.

Independent check: scripts/check_membership_wayback.py compares month-ends
with Wayback Machine snapshots of the same pages.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts.sync_universe import EXPECTED, HEADERS, parse_list, to_yahoo  # noqa: E402

API = "https://en.wikipedia.org/w/api.php"
TITLES = {"S&P 500": "List of S&P 500 companies", "S&P 400": "List of S&P 400 companies",
          "S&P 600": "List of S&P 600 companies"}
CACHE = os.environ.get("WIKI_CACHE", os.path.join(ROOT, "data_cache", "wikirev"))
TIMELINE = os.path.join(ROOT, "data", "membership_history.json")
MONTHLY = os.path.join(ROOT, "data", "membership_monthly.csv")
RANK = {"S&P 500": 0, "S&P 400": 1, "S&P 600": 2}


def _get(s: requests.Session, params: dict) -> dict:
    """One API call, paced and retried on 429/5xx (Wikimedia rate limits)."""
    wait = 5.0
    for _ in range(8):
        r = s.get(API, params={**params, "maxlag": 5}, headers=HEADERS, timeout=90)
        if r.status_code == 200:
            try:
                j = r.json()
            except ValueError:
                j = None
            if j is not None and "error" not in j:
                time.sleep(1.0)
                return j
        delay = float(r.headers.get("Retry-After") or wait)
        print(f"  wikipedia {r.status_code}; waiting {delay:.0f}s", flush=True)
        time.sleep(delay)
        wait = min(wait * 2, 120)
    raise RuntimeError(f"Wikipedia API refused {params.get('action')} after retries")


def revisions(title: str, start: str, s: requests.Session) -> pd.DataFrame:
    """Every revision (id, timestamp) of ``title`` from a month before ``start``."""
    rows, cont = [], {}
    begin = (pd.Timestamp(start) - pd.DateOffset(months=2)).strftime("%Y-%m-%dT00:00:00Z")
    while True:
        params = {"action": "query", "prop": "revisions", "titles": title, "rvlimit": 500,
                  "rvprop": "ids|timestamp", "rvdir": "newer", "rvstart": begin, "format": "json", **cont}
        j = _get(s, params)
        for page in j["query"]["pages"].values():
            rows += [(r["revid"], r["timestamp"]) for r in page.get("revisions", [])]
        if "continue" not in j:
            break
        cont = j["continue"]
    df = pd.DataFrame(rows, columns=["revid", "ts"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return df.sort_values("ts")


def revision_html(revid: int, s: requests.Session) -> str:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{revid}.html")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    j = _get(s, {"action": "parse", "oldid": revid, "prop": "text", "format": "json"})
    html = j["parse"]["text"]["*"]
    open(path, "w", encoding="utf-8").write(html)
    return html


def month_ends(start: str, end: pd.Timestamp) -> list[pd.Timestamp]:
    """Each month's last NYSE session from ``start`` to ``end``."""
    import exchange_calendars as xcals

    cal = xcals.get_calendar("XNYS")
    sess = pd.DatetimeIndex(cal.sessions_in_range(pd.Timestamp(start), end)).tz_localize(None)
    return list(pd.Series(sess, index=sess).groupby(sess.to_period("M")).max())


def build(start: str) -> tuple[pd.DataFrame, list[str]]:
    s = requests.Session()
    today = pd.Timestamp.today().normalize()
    ends = [d for d in month_ends(start, today) if d < today.to_period("M").start_time]
    out, notes = [], []
    skipped: dict[str, list] = {}
    for index, title in TITLES.items():
        revs = revisions(title, start, s)
        lo, hi = EXPECTED[index]
        for d in ends:
            # The page as it stood at the close (16:00 New York) of the month-end.
            before = revs[revs["ts"] <= d + pd.Timedelta(hours=16)]
            if before.empty:
                notes.append(f"{index} {d.date()}: no revision yet")
                continue
            revid = int(before["revid"].iloc[-1])
            df = parse_list(revision_html(revid, s), index)
            if not lo - 10 <= len(df) <= hi + 10:
                notes.append(f"{index} {d.date()}: {len(df)} rows in revision {revid}, outside {lo}-{hi}; "
                             "rebuilt from the change log instead")
                skipped.setdefault(index, []).append(d)
                continue
            df["Date"], df["revid"] = d, revid
            out.append(df)
        print(f"{index}: {len(revs)} revisions, {len(ends)} month-ends", flush=True)
    monthly = pd.concat(out, ignore_index=True)
    for index, missing in skipped.items():
        monthly = pd.concat([monthly, backfill(monthly, index, missing, changelog(index, s))], ignore_index=True)
    return monthly, notes


def changelog(index: str, s: requests.Session) -> pd.DataFrame:
    """The current page's dated change log: Date, Added, Removed (Yahoo symbols)."""
    title = TITLES[index]
    j = _get(s, {"action": "parse", "page": title, "prop": "text", "format": "json"})
    for t in pd.read_html(io.StringIO(j["parse"]["text"]["*"])):
        if isinstance(t.columns, pd.MultiIndex) and len(t.columns) >= 5:
            t = t.iloc[:, :5]
            t.columns = ["Date", "AddT", "AddS", "RemT", "RemS"]
            t["Date"] = pd.to_datetime(t["Date"], errors="coerce")
            t = t.dropna(subset=["Date"])
            return pd.DataFrame({
                "Date": t["Date"],
                "Added": t["AddT"].map(lambda x: to_yahoo(x) if isinstance(x, str) else None),
                "Removed": t["RemT"].map(lambda x: to_yahoo(x) if isinstance(x, str) else None)})
    return pd.DataFrame(columns=["Date", "Added", "Removed"])


def backfill(monthly: pd.DataFrame, index: str, missing: list[pd.Timestamp], log: pd.DataFrame) -> pd.DataFrame:
    """Month-ends the page could not give, rebuilt by undoing the dated change log
    from the first good month-end after them. Checked 10 Nov 2026 on real snapshots:
    S&P 600 Dec 2022 undone to Mar 2021 agrees on 592 of 601 names."""
    good = sorted(set(monthly[monthly["Index"] == index]["Date"]))
    out = []
    for t in missing:
        later = [g for g in good if g > t]
        if not later:
            continue
        anchor = later[0]
        base = monthly[(monthly["Index"] == index) & (monthly["Date"] == anchor)]
        members = dict(zip(base["Yahoo"], base.to_dict("records")))
        for r in log[(log["Date"] > t) & (log["Date"] <= anchor)].sort_values("Date", ascending=False).itertuples():
            if r.Added:
                members.pop(r.Added, None)
            if r.Removed:
                members.setdefault(r.Removed, {"Symbol": r.Removed.replace("-", "."), "Yahoo": r.Removed,
                                               "Company": r.Removed, "Sector": "", "Industry": "", "Index": index})
        df = pd.DataFrame(list(members.values()))
        df["Date"], df["revid"] = t, -1
        out.append(df)
        print(f"  {index} {t.date()}: rebuilt from the change log ({len(df)} names, anchored {anchor.date()})")
    return pd.concat(out, ignore_index=True) if out else monthly.iloc[0:0]


# Name matches that are NOT the same security's history (checked by hand, 10 Nov 2026):
REJECTED_ALIASES = {
    "IBTX": "Independent Bank Group (Texas) is not Independent Bank Corp (INDB, Massachusetts); "
            "both were S&P 600 members at the same time",
    "SIX": "Six Flags merged into Cedar Fair in 2024; the survivor trades as FUN, whose earlier "
           "prices are Cedar Fair's, not Six Flags'",
}


def aliases(monthly: pd.DataFrame, current: pd.DataFrame) -> dict:
    """Old ticker -> today's, where the company name matches, the ticker differs,
    and the two never sat on the lists at the same month-end (a rename is a
    hand-over; two live members with similar names are two companies)."""
    def key(name: str) -> str:
        n = re.sub(r"[^a-z0-9 ]", "", str(name).lower())
        n = re.sub(r"\b(inc|corp|corporation|co|company|ltd|plc|group|holdings|the|class [a-z])\b", "", n)
        return " ".join(n.split())
    now = {key(n): y for n, y in zip(current["Company"], current["Yahoo"])}
    dates = monthly.groupby("Yahoo")["Date"].apply(set).to_dict()
    # CIK first (exact across renames), the name second.
    cik_col = monthly["CIK"] if "CIK" in monthly else pd.Series("", index=monthly.index)
    latest = monthly.assign(CIK=cik_col.fillna("")).sort_values("Date")
    cik_of = {s: c for s, c in zip(latest["Yahoo"], latest["CIK"]) if c}
    now_month = latest["Date"].max()
    cik_now = {c: s for s, c, d in zip(latest["Yahoo"], latest["CIK"], latest["Date"])
               if c and d == now_month and s in set(current["Yahoo"])}
    out = {}
    for sym, name in monthly.drop_duplicates("Yahoo")[["Yahoo", "Company"]].itertuples(index=False):
        by_cik = cik_now.get(cik_of.get(sym, ""))
        new = by_cik or now.get(key(name))
        if not new or new == sym or sym in set(current["Yahoo"]) or sym in REJECTED_ALIASES:
            continue
        if dates.get(sym, set()) & dates.get(new, set()):
            continue    # both listed at once: not a rename
        out[sym] = {"new_symbol": new, "matched_on": f"CIK {cik_of[sym]}" if by_cik else str(name)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default="2019-12")
    args = ap.parse_args(argv)
    from scripts.sync_universe import combine
    from src.engine import membership as mem

    monthly, notes = build(args.start + "-01")
    for n in notes:
        print("  note:", n)
    rows = []
    for d, g in monthly.groupby("Date"):
        one = combine([g])
        one["Date"] = d
        rows.append(one)
    m = pd.concat(rows, ignore_index=True)
    if "CIK" not in m:
        m["CIK"] = ""
    m[["Date", "Index", "Symbol", "Yahoo", "Company", "Sector", "CIK"]].sort_values(["Date", "Symbol"]).to_csv(
        MONTHLY, index=False, date_format="%Y-%m-%d")

    current = pd.read_csv(os.path.join(ROOT, "data", "universe.csv"), dtype=str, keep_default_na=False)
    hist = mem.empty_history("S&P 1500")
    for d in sorted(m["Date"].unique()):
        hist, _ = mem.record_snapshot(hist, pd.Timestamp(d).date(), m[m["Date"] == d]["Yahoo"])
    as_of = current["AsOf"].iloc[0]
    if pd.Timestamp(as_of) > pd.Timestamp(m["Date"].max()):
        hist, _ = mem.record_snapshot(hist, as_of, current["Yahoo"])
    hist["aliases"] = aliases(m, current)
    hist["source"] = ("Wikipedia revision history of the S&P 500/400/600 lists, the last revision "
                      "on or before each month-end close; today's snapshot from scripts/sync_universe.py")
    hist["caveats"] = notes
    hist["rejected_aliases"] = REJECTED_ALIASES
    mem.save_history(hist, TIMELINE)
    ever = set(hist["baseline"]["symbols"]).union(*[set(c["added"]) for c in hist["changes"]])
    print(f"timeline {hist['baseline']['date']} .. {as_of}: {len(hist['changes'])} change dates, "
          f"{len(ever)} symbols ever, {len(hist['aliases'])} ticker aliases")
    print(json.dumps(dict(list(hist["aliases"].items())[:12]), indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
