"""Internal audit of the stored prices. Run after every sync.

Checks, per symbol, on the split-adjusted close:
  * ratio   -- a one-day move within 3% of a split ratio (2, 3, 4, 1/2, ...):
               on a recorded split day the split was NOT applied, on any other
               day a split went unrecorded;
  * spike   -- a move beyond JUMP that the next session undoes to within 10%
               of the earlier close (a bad print);
  * jumps   -- any other move beyond JUMP: reported, not failed. US small caps
               and biotechs make real 45%+ moves (trial results, 2008), and a
               penny stock's one-cent tick is 50%;
  * gaps    -- NYSE sessions between the symbol's first and last row with no
               row (halts exist, but each one is listed);
  * stale   -- STALE or more sessions in a row with the same close and zero volume;
  * bounds  -- High < Close or Low > Close, or a non-positive price;
  * last    -- a CURRENT member whose latest row is more than LAST_LAG sessions
               behind the store (acquired or delisted while still on the
               Wikipedia list: QRVO, last row 2026-10-02, seen 10 Nov 2026).

Writes ``reports/price_audit_<date>.csv``. Exit 1 on any unexplained ratio,
spike or bounds finding in the last RECENT sessions (what the ranking and the
backtest read), so the workflow turns red. Older findings are listed as
history: Yahoo does not adjust spin-offs (EXPE 2011-12-21, TripAdvisor: a
1-for-2 split and a $15.125 "dividend" recorded, the price still halves), and
an old unadjusted event cannot reach a 12-month ranking; gaps and stale runs are reported
only (a halt is real), and ``data/price_exceptions.csv`` lists findings that
were checked against another source and explained.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core import market_time as mt  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402

JUMP = 0.45
STALE = 5
RECENT = 400
LAST_LAG = 5
SPLIT_RATIOS = [2, 3, 4, 5, 10, 20, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 10, 1 / 20]
RATIO_TOL = 0.01
EXCEPTIONS_FILE = os.path.join(ROOT, "data", "price_exceptions.csv")


def sessions_between(a: pd.Timestamp, b: pd.Timestamp) -> pd.DatetimeIndex:
    import exchange_calendars as xcals

    cal = xcals.get_calendar("XNYS")
    a = max(pd.Timestamp(a), cal.first_session)
    return pd.DatetimeIndex(cal.sessions_in_range(a, pd.Timestamp(b))).tz_localize(None)


def audit(long: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    out = []
    close = ps.wide(long, "Close")
    vol = ps.wide(long, "Volume")
    splits = actions[actions["Split"] > 0] if len(actions) else actions
    split_days = {(s, pd.Timestamp(d)) for s, d in zip(splits.get("Symbol", []), splits.get("Date", []))}
    sessions = sessions_between(close.index.min(), close.index.max())

    for sym in close.columns:
        c = close[sym].dropna()
        if c.empty:
            continue
        r = c / c.shift(1)
        nxt = c.shift(-1) / c.shift(1)
        for d in r.index[1:]:
            x = r.loc[d]
            if not np.isfinite(x) or abs(x - 1) <= 0.3:
                continue
            on_split = (sym, d) in split_days
            if any(abs(x / k - 1) < RATIO_TOL for k in SPLIT_RATIOS):
                why = "on a recorded split day: not applied" if on_split else "no split recorded"
                out.append((sym, str(d.date()), "ratio", f"x{x:.3f} {why}"))
            elif abs(x - 1) > JUMP and np.isfinite(nxt.loc[d]) and abs(nxt.loc[d] - 1) < 0.10:
                out.append((sym, str(d.date()), "spike", f"{x - 1:+.1%} then back to {nxt.loc[d] - 1:+.1%}"))
            elif abs(x - 1) > JUMP and not on_split:
                out.append((sym, str(d.date()), "jump", f"{x - 1:+.1%}"))
        span = sessions[(sessions >= c.index.min()) & (sessions <= c.index.max())]
        missing = span.difference(c.index)
        if len(missing):
            out.append((sym, str(missing[0].date()), "gaps", f"{len(missing)} sessions, first {missing[0].date()} last {missing[-1].date()}"))
        v = vol[sym].reindex(c.index).fillna(0)
        same = (c.diff() == 0) & (v == 0)
        run = same.groupby((~same).cumsum()).cumsum()
        if run.max() >= STALE:
            d = run.idxmax()
            out.append((sym, str(d.date()), "stale", f"{int(run.max())} sessions unchanged with no volume"))

    newest = close.index.max()
    lag_from = sessions[sessions <= newest][-(LAST_LAG + 1)] if len(sessions) > LAST_LAG else newest
    universe = set(pd.read_csv(os.path.join(ROOT, "data", "universe.csv"))["Yahoo"])
    for sym in sorted(universe & set(close.columns)):
        last = close[sym].last_valid_index()
        if last is not None and last < lag_from:
            out.append((sym, str(last.date()), "last", f"latest row {last.date()}, store at {newest.date()}"))

    bad = long[(long["Close"] <= 0) | (long["High"] < long["Close"] * 0.999) | (long["Low"] > long["Close"] * 1.001)]
    for sym, d in zip(bad["Symbol"], bad["Date"]):
        out.append((sym, str(pd.Timestamp(d).date()), "bounds", "high/low inconsistent with close"))
    return pd.DataFrame(out, columns=["Symbol", "Date", "Check", "Detail"])



def confirm_with_nasdaq(rep: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """For each recent ratio/spike finding, ask Nasdaq.com (official closes,
    independent of Yahoo) whether the same session shows the same move. Agreement
    within 2 points explains it as a real move; disagreement leaves it failing."""
    import time

    from scripts.audit_nasdaq import nasdaq_history

    rep = rep.copy()
    rep["Nasdaq"] = ""
    todo = rep[rep["Check"].isin(["ratio", "spike"]) & rep["Recent"] & ~rep["Explained"]]
    for i, row in todo.iterrows():
        d = pd.Timestamp(row["Date"])
        try:
            # The API answers nothing for a window that ends in the past
            # (probed 10 Nov 2026): ask up to today and slice.
            off = nasdaq_history(row["Symbol"], str((d - pd.Timedelta(days=10)).date()), str(mt.ny_today()))
        except Exception as exc:  # noqa: BLE001
            rep.at[i, "Nasdaq"] = f"unavailable ({type(exc).__name__})"
            continue
        time.sleep(0.5)
        if d not in off.index or off.index.get_loc(d) == 0:
            rep.at[i, "Nasdaq"] = "no row for the session"
            continue
        theirs = off.loc[d] / off.iloc[off.index.get_loc(d) - 1] - 1
        c = close[row["Symbol"]].dropna()
        ours = c.loc[d] / c.iloc[c.index.get_loc(d) - 1] - 1
        agree = abs(theirs - ours) < 0.02
        rep.at[i, "Nasdaq"] = f"Nasdaq {theirs:+.1%}, ours {ours:+.1%}"
        if agree:
            rep.at[i, "Explained"] = True
    return rep


FORMER_FILE = os.path.join(ROOT, "data", "former_members.csv")
AFTER_LEAVING = pd.Timedelta(days=45)


def former_cutoffs() -> dict[str, pd.Timestamp]:
    """A former member's rows are judged only to shortly after it left the
    index: nothing reads them later (EGRX left in May 2023; its 2025-26 Yahoo
    rows, from over-the-counter trading, are junk and irrelevant)."""
    if not os.path.exists(FORMER_FILE):
        return {}
    f = pd.read_csv(FORMER_FILE, parse_dates=["LastMember"])
    return {s: d + AFTER_LEAVING for s, d in zip(f["Symbol"], f["LastMember"]) if pd.notna(d)}


def main() -> int:
    long = ps.read_long()
    current = set(pd.read_csv(os.path.join(ROOT, "data", "universe.csv"))["Yahoo"])
    cut = {s: d for s, d in former_cutoffs().items() if s not in current}
    if cut:
        limit = long["Symbol"].map(cut)
        long = long[limit.isna() | (long["Date"] <= limit)]
    rep = audit(long, ps.read_actions())
    if rep.empty:
        rep = pd.DataFrame(columns=["Symbol", "Date", "Check", "Detail"])
    if os.path.exists(EXCEPTIONS_FILE):
        ex = pd.read_csv(EXCEPTIONS_FILE, dtype=str)
        key = set(zip(ex["Symbol"], ex["Date"], ex["Check"]))
        rep["Explained"] = [(s, d, c) in key for s, d, c in zip(rep["Symbol"], rep["Date"], rep["Check"])]
    else:
        rep["Explained"] = False
    recent_from = str(sorted(long["Date"].unique())[-RECENT].date()) if long["Date"].nunique() > RECENT else "0000"
    rep["Recent"] = rep["Date"] >= recent_from
    if "--no-nasdaq" not in sys.argv:
        rep = confirm_with_nasdaq(rep, ps.wide(long, "Close"))
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    out = os.path.join(ROOT, "reports", f"price_audit_{mt.ny_today()}.csv")
    rep.to_csv(out, index=False)
    print(f"{long['Symbol'].nunique()} symbols, {len(long):,} rows, {long['Date'].min().date()} to {long['Date'].max().date()}")
    print(rep.groupby(["Check", "Recent", "Explained"]).size().to_string() if len(rep) else "no findings")
    failing = rep[(rep["Check"].isin(["ratio", "spike", "bounds"]) & rep["Recent"] | (rep["Check"] == "last")) & ~rep["Explained"]]
    if len(failing):
        print("unexplained:")
        print(failing.head(60).to_string(index=False))
    print(f"report: {out}")
    return 1 if len(failing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
