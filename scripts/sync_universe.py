"""S&P 1500 membership from Wikipedia's constituent lists.

S&P Dow Jones Indices does not publish free constituent files, and yfinance has
no index-membership endpoint. Wikipedia's three lists (S&P 500, MidCap 400,
SmallCap 600) carry the current members with their GICS sector and
sub-industry, and are maintained within days of each S&P announcement.

Writes:
  data/universe.csv            today's members (one row per symbol)
  data/membership_history.csv  Symbol, Index, From, To -- built forward from
                               dated snapshots: a symbol that leaves gets a To
                               date, one that arrives gets a From date.

Point-in-time membership before the first snapshot is NOT reconstructed here;
see docs/DATA_CORRECTNESS.md (survivorship).
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import date

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core.market_time import ny_today  # noqa: E402

LISTS = {
    "S&P 500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "S&P 400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "S&P 600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}
# Bounds a sane scrape must fall within; a page edit that drops a table or
# halves it fails loudly instead of silently shrinking the universe.
EXPECTED = {"S&P 500": (495, 510), "S&P 400": (395, 405), "S&P 600": (595, 610)}
HEADERS = {"User-Agent": "us-momentum-terminal/1.0 (index membership sync)"}
UNIVERSE_FILE = os.path.join(ROOT, "data", "universe.csv")
HISTORY_FILE = os.path.join(ROOT, "data", "membership_history.csv")
# The engine's point-in-time timeline (Paresh's format: baseline + dated
# changes), in Yahoo symbols, for the whole S&P 1500.
TIMELINE_FILE = os.path.join(ROOT, "data", "membership_history.json")
# Every symbol ever on the list with the GICS sector it last carried, so a
# member that leaves can still be placed by the backtest's sector cap.
SECTOR_HISTORY_FILE = os.path.join(ROOT, "data", "sector_history.csv")
COLUMNS = ["Symbol", "Yahoo", "Company", "Sector", "Industry", "Index"]


def to_yahoo(symbol: str) -> str:
    """Wikipedia/S&P write share classes with a dot (BRK.B); Yahoo uses a dash."""
    return symbol.strip().upper().replace(".", "-")


def _col(cols: list[str], *needles: str, avoid: str | None = None) -> str | None:
    for c in cols:
        low = c.lower()
        if any(n in low for n in needles) and not (avoid and avoid in low):
            return c
    return None


def parse_list(html: str, index: str) -> pd.DataFrame:
    """The constituent table, wherever its columns sit and whatever the page
    called them in that revision ("GICS Sub-Industry", "GICS Sub Industry",
    "Ticker symbol", "Company", "GICS Economic Sector", ...)."""
    for t in pd.read_html(io.StringIO(html)):
        if isinstance(t.columns, pd.MultiIndex):
            continue
        cols = [str(c) for c in t.columns]
        sym = _col(cols, "symbol", "ticker")
        sector = _col(cols, "sector", avoid="sub")
        sub = _col(cols, "sub-industry", "sub industry", "subindustry", "industry")
        name = _col(cols, "security", "company", "name")
        cik = _col(cols, "cik")
        if not (sym and sector and sub) or len(t) < 100:
            continue
        out = pd.DataFrame({
            "Symbol": t[sym].astype(str).str.strip().str.upper(),
            "Company": t[name].astype(str).str.strip() if name else t[sym].astype(str),
            "Sector": t[sector].astype(str).str.strip(),
            "Industry": t[sub].astype(str).str.strip(),
        })
        # The SEC's company number: it survives a rename, unlike the ticker or
        # the name (Anthem -> Elevance, Alliance Data -> Bread Financial).
        out["CIK"] = (pd.to_numeric(t[cik], errors="coerce").map(lambda v: f"{int(v):010d}" if pd.notna(v) else "")
                      if cik else "")
        out = out[out["Symbol"].str.match(r"^[A-Z][A-Z0-9.\-]*$")]
        out["Yahoo"] = out["Symbol"].map(to_yahoo)
        out["Index"] = index
        return out[COLUMNS + ["CIK"]]
    raise ValueError(f"{index}: no constituent table found on the page")


def fetch(session: requests.Session | None = None) -> pd.DataFrame:
    s = session or requests.Session()
    frames = []
    for index, url in LISTS.items():
        r = s.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        df = parse_list(r.text, index)
        lo, hi = EXPECTED[index]
        if not lo <= len(df) <= hi:
            raise ValueError(f"{index}: {len(df)} rows, expected {lo}-{hi}")
        frames.append(df)
    return combine(frames)


def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """One row per symbol. A stock moving between the 400 and 600 can sit on
    both pages for a few days while editors catch up; the larger index wins."""
    rank = {"S&P 500": 0, "S&P 400": 1, "S&P 600": 2}
    u = pd.concat(frames, ignore_index=True)
    u["_r"] = u["Index"].map(rank)
    u = u.sort_values(["Symbol", "_r"]).drop_duplicates("Symbol").drop(columns="_r")
    return u.sort_values("Symbol").reset_index(drop=True)


def update_history(history: pd.DataFrame, current: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Close the spells of symbols that left (or changed index), open new ones."""
    cols = ["Symbol", "Index", "From", "To"]
    h = history.copy() if len(history) else pd.DataFrame(columns=cols)
    h["To"] = h["To"].fillna("").astype(str)
    open_ = h[h["To"] == ""]
    now = set(zip(current["Symbol"], current["Index"]))
    was = set(zip(open_["Symbol"], open_["Index"]))
    for sym, idx in was - now:
        m = (h["Symbol"] == sym) & (h["Index"] == idx) & (h["To"] == "")
        h.loc[m, "To"] = as_of
    new = pd.DataFrame(sorted(now - was), columns=["Symbol", "Index"])
    new["From"], new["To"] = as_of, ""
    h = pd.concat([h, new], ignore_index=True)
    return h[cols].sort_values(["Symbol", "From"]).reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=None, help="snapshot date (default: today in New York)")
    args = ap.parse_args(argv)
    as_of = args.as_of or ny_today().isoformat()
    date.fromisoformat(as_of)

    current = fetch()
    hist = pd.read_csv(HISTORY_FILE, dtype=str, keep_default_na=False) if os.path.exists(HISTORY_FILE) else pd.DataFrame()
    hist = update_history(hist, current, as_of)

    from src.engine import membership as mem

    timeline = mem.load_history(TIMELINE_FILE) if os.path.exists(TIMELINE_FILE) else mem.empty_history("S&P 1500")
    first, last = mem.coverage(timeline)
    changed_any = False
    if last is None or date.fromisoformat(as_of) > last:
        timeline, changed_any = mem.record_snapshot(timeline, as_of, current["Yahoo"])
    # The per-index timelines (the main book reads "sp500").
    for name, key in {"S&P 500": "sp500", "S&P 400": "sp400", "S&P 600": "sp600"}.items():
        sub = (timeline.get("indices") or {}).get(key)
        if not sub:
            continue
        subh = {"baseline": sub["baseline"], "changes": list(sub["changes"])}
        _f, sub_last = mem.coverage(subh)
        if sub_last is None or date.fromisoformat(as_of) > sub_last:
            subh, ch = mem.record_snapshot(subh, as_of, current[current["Index"] == name]["Yahoo"])
            if ch:
                timeline["indices"][key] = {"baseline": subh["baseline"], "changes": subh["changes"]}
                changed_any = True
    if changed_any:
        mem.save_history(timeline, TIMELINE_FILE)

    sh = pd.read_csv(SECTOR_HISTORY_FILE, dtype=str, keep_default_na=False) if os.path.exists(SECTOR_HISTORY_FILE) else pd.DataFrame(columns=["Symbol", "Sector", "LastSeen"])
    now = pd.DataFrame({"Symbol": current["Yahoo"], "Sector": current["Sector"], "LastSeen": as_of})
    sh = pd.concat([sh[~sh["Symbol"].isin(now["Symbol"])], now]).sort_values("Symbol")
    sh.to_csv(SECTOR_HISTORY_FILE, index=False)

    current.assign(AsOf=as_of).to_csv(UNIVERSE_FILE, index=False)
    hist.to_csv(HISTORY_FILE, index=False)
    print(f"universe {len(current)} symbols as of {as_of}: "
          + ", ".join(f"{k} {v}" for k, v in current['Index'].value_counts().sort_index().items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
