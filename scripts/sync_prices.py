"""Nightly US price sync from Yahoo (yfinance) into the committed store.

  python scripts/sync_prices.py --backfill      # every member from START
  python scripts/sync_prices.py                 # nightly: the recent sessions

The nightly run is idempotent and safe to start twice (the workflow does, to
cover daylight saving and GitHub's late starts): it asks only for sessions the
NYSE calendar says have settled (``market_time.last_downloadable_session``),
writes a file only when its content changed, and exits 0 with "up to date" when
there is nothing new.

What it refuses to write:
  * a session that is not an NYSE session, or has not settled yet;
  * a new session that fewer than MIN_COVERAGE of the universe have reached
    (Yahoo publishing late, or blocking us) -- the next run tries again;
  * a symbol whose recent history disagrees with what is stored, unless the
    disagreement is explained by a split: then its whole history is fetched
    again and replaced everywhere (Yahoo restates split-adjusted prices).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core import market_time as mt  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402

START = "2008-01-01"
CHUNK = 150
RETRIES = 4
MIN_COVERAGE = 0.97
OVERLAP_SESSIONS = 10
RESTATE_TOLERANCE = 0.002      # 0.2% median disagreement on the overlap
UNIVERSE_FILE = os.path.join(ROOT, "data", "universe.csv")
BENCHMARK_FILE = os.path.join(ROOT, "data", "benchmarks.csv")
# SPY: the S&P 500 benchmark (dividend-adjusted as SPY_TR); SPTM: the S&P 1500
# ETF (Yahoo's ^SP1500 has no history); the three S&P price indices.
BENCHMARKS = ["SPY", "SPTM", "^GSPC", "^SP400", "^SP600"]


def log(msg: str) -> None:
    print(msg, flush=True)


def universe() -> list[str]:
    return sorted(pd.read_csv(UNIVERSE_FILE)["Yahoo"].astype(str).unique())


def _download(tickers: list[str], start: str | None) -> pd.DataFrame:
    import yfinance as yf

    last = None
    for attempt in range(RETRIES):
        try:
            # No start means the whole history: yfinance's own default is one month.
            span = {"start": start} if start else {"period": "max"}
            df = yf.download(tickers, **span, interval="1d", auto_adjust=False,
                             actions=True, group_by="column", threads=True,
                             progress=False, timeout=60)
            if df is not None and not df.empty:
                return df
            last = "empty response"
        except Exception as exc:  # noqa: BLE001 - network faults are retried
            last = f"{type(exc).__name__}: {exc}"
        wait = 2 ** (attempt + 1)
        log(f"  download attempt {attempt + 1} failed ({last}); retry in {wait}s")
        time.sleep(wait)
    raise RuntimeError(f"Yahoo download failed after {RETRIES} attempts: {last}")


def to_long(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """yfinance's wide frame -> (prices long, actions long)."""
    if not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError("expected yfinance column MultiIndex (field, ticker)")
    s = raw.stack(level=1, future_stack=True)
    s.index.names = ["Date", "Symbol"]
    s = s.reset_index()
    prices = s.dropna(subset=["Close"])[["Date", "Symbol", "High", "Low", "Close", "Volume"]]
    a = s.rename(columns={"Dividends": "Dividend", "Stock Splits": "Split"})
    for c in ("Dividend", "Split"):
        if c not in a:
            a[c] = 0.0
    a[["Dividend", "Split"]] = a[["Dividend", "Split"]].fillna(0.0)
    actions = a[(a["Dividend"] != 0) | (a["Split"] != 0)][ps.ACTION_COLS]
    return ps.normalise(prices), actions


def fetch(tickers: list[str], start: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every chunk of ``tickers``. A chunk of a few tickers that Yahoo answers
    empty (a delisted or unserved symbol) is reported and skipped; the run
    fails only when a large chunk is empty, which means Yahoo refused us."""
    px, ac = [], []
    for i in range(0, len(tickers), CHUNK):
        part = tickers[i:i + CHUNK]
        log(f"  fetching {i + 1}-{i + len(part)} of {len(tickers)} from {start}")
        try:
            raw = _download(part, start)
        except RuntimeError:
            if len(part) <= 10:
                log(f"::warning::Yahoo served nothing for {' '.join(part)}")
                continue
            raise
        p, a = to_long(raw)
        px.append(p)
        ac.append(a)
    if not px:
        return ps.normalise(None), pd.DataFrame(columns=ps.ACTION_COLS)
    return (ps.normalise(pd.concat(px, ignore_index=True)),
            pd.concat(ac, ignore_index=True) if ac else pd.DataFrame(columns=ps.ACTION_COLS))


LAST_LAG = 5


def _stale(stored: pd.DataFrame, sym: str, target) -> bool:
    """No stored row for ``sym`` in the last LAST_LAG sessions before ``target``."""
    rows = stored[stored["Symbol"] == sym]
    if rows.empty:
        return True
    recent = mt.recent_trading_days(LAST_LAG + 1, as_of=pd.Timestamp(target).date())
    return pd.Timestamp(rows["Date"].max()).date() < min(recent)


def settled_only(long: pd.DataFrame, target) -> pd.DataFrame:
    """Drop rows after the last settled session and rows on non-sessions."""
    if long.empty:
        return long
    keep = long["Date"] <= pd.Timestamp(target)
    sessions = {d for d in long["Date"].unique() if mt.is_session(pd.Timestamp(d).date())}
    return long[keep & long["Date"].isin(sessions)].reset_index(drop=True)


def restated(stored: pd.DataFrame, fresh: pd.DataFrame) -> list[str]:
    """Symbols whose overlap closes disagree with what is stored."""
    if stored.empty or fresh.empty:
        return []
    m = stored.merge(fresh, on=["Date", "Symbol"], suffixes=("_s", "_f"))
    if m.empty:
        return []
    m["r"] = (m["Close_f"] / m["Close_s"] - 1.0).abs()
    med = m.groupby("Symbol")["r"].median()
    return sorted(med[med > RESTATE_TOLERANCE].index)


def coverage_ok(new_rows: pd.DataFrame, n_universe: int) -> tuple[pd.DataFrame, list[str]]:
    """Keep only new sessions that enough of the universe has reached."""
    notes = []
    if new_rows.empty:
        return new_rows, notes
    counts = new_rows.groupby("Date")["Symbol"].nunique()
    good = counts[counts >= MIN_COVERAGE * n_universe].index
    for d, n in counts.items():
        if d not in good:
            notes.append(f"{pd.Timestamp(d).date()}: {n}/{n_universe} symbols, held back")
    return new_rows[new_rows["Date"].isin(good)], notes


def sync_benchmarks(target) -> None:
    p, _ = fetch(BENCHMARKS, START)
    p = settled_only(p, target)
    w = ps.wide(p, "Close")
    import yfinance as yf  # adjusted (total return) closes for the two ETFs
    adj = yf.download(["SPY", "SPTM"], start=START, auto_adjust=True, progress=False)["Close"]
    adj.index = pd.to_datetime(adj.index).tz_localize(None)
    w["SPTM_TR"] = adj["SPTM"].reindex(w.index)
    w["SPY_TR"] = adj["SPY"].reindex(w.index)
    w = w.round(4)
    text = w.to_csv(date_format="%Y-%m-%d")
    if not os.path.exists(BENCHMARK_FILE) or open(BENCHMARK_FILE).read() != text:
        with open(BENCHMARK_FILE, "w") as fh:
            fh.write(text)
        log(f"benchmarks written to {w.index.max().date()}")


def run(backfill: bool = False, now=None) -> int:
    target = mt.last_downloadable_session(now=now)
    if target is None:
        log("no settled session in the lookback window; nothing to do")
        return 0
    syms = universe()
    today = mt.ny_today() if now is None else now.astimezone(mt.NY_TZ).date()
    stored = ps.read_long(start=str(pd.Timestamp(target) - pd.Timedelta(days=40)))
    have = set(stored["Symbol"]) if not backfill else set()
    latest = stored["Date"].max() if len(stored) else None

    if not backfill and latest is not None and pd.Timestamp(latest) >= pd.Timestamp(target):
        # Members with no row for LAST_LAG sessions (acquired or delisted while
        # still listed, or never served by Yahoo) cannot make the store current
        # and must not make every run a full refetch.
        on_target = set(ps.read_long(start=str(target))["Symbol"])
        live = {s for s in syms if s in have and not _stale(stored, s, target)}
        if live <= on_target:
            log(f"up to date: store holds {pd.Timestamp(latest).date()}, last settled session {target}"
                f" ({len(set(syms) - live)} member(s) without recent prices not counted)")
            return 0

    actions_all = ps.read_actions()
    if backfill:
        prices, actions = fetch(syms, START)
        prices = settled_only(prices, target)
        written = ps.store(prices, today)
        ps.write_actions(actions)
        log(f"backfill: {prices['Symbol'].nunique()} symbols, {len(prices):,} rows, {len(written)} files")
        missing = sorted(set(syms) - set(prices["Symbol"]))
        if missing:
            log(f"no Yahoo history for {len(missing)}: {' '.join(missing[:30])}")
    else:
        # A member never stored is fetched in full once; one Yahoo has stopped
        # serving (stale) is not asked again every night.
        new_syms = sorted(set(syms) - have)
        old_syms = sorted(set(syms) & have)
        start = str((pd.Timestamp(target) - pd.tseries.offsets.BDay(OVERLAP_SESSIONS + 5)).date())
        fresh, fresh_actions = fetch(old_syms, start) if old_syms else (ps.normalise(None), pd.DataFrame(columns=ps.ACTION_COLS))
        fresh = settled_only(fresh, target)

        redo = restated(stored, fresh)
        if redo:
            log(f"restated by Yahoo (refetching whole history): {' '.join(redo)}")
        full_syms = sorted(set(new_syms) | set(redo))
        full, full_actions = fetch(full_syms, START) if full_syms else (ps.normalise(None), pd.DataFrame(columns=ps.ACTION_COLS))
        full = settled_only(full, target)

        fresh = fresh[~fresh["Symbol"].isin(redo)]
        newest_stored = pd.Timestamp(latest) if latest is not None else pd.Timestamp(START)
        old_part = fresh[fresh["Date"] <= newest_stored]
        new_part, notes = coverage_ok(fresh[fresh["Date"] > newest_stored], len(syms))
        for n in notes:
            log(n)
        written = ps.store(pd.concat([old_part, new_part], ignore_index=True), today)
        for sym in sorted(set(full["Symbol"])):
            written += ps.replace_symbol(sym, full[full["Symbol"] == sym], today)
        # A refetched symbol's actions come only from its fresh full history.
        kept = actions_all[~actions_all["Symbol"].isin(full_syms)]
        acts = pd.concat([kept, fresh_actions[~fresh_actions["Symbol"].isin(full_syms)], full_actions],
                         ignore_index=True)
        ps.write_actions(acts)
        log(f"update to {target}: {len(set(written))} files written; new symbols {len(new_syms)}, restated {len(redo)}")
        if notes:
            # A held-back session is not a failure of this run, but it must be seen.
            log("::warning::" + "; ".join(notes))

    rolled = ps.roll_up(today)
    if rolled:
        log(f"rolled up {len(rolled) // 2} closed period file(s)")
    sync_benchmarks(target)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args(argv)
    np.seterr(all="ignore")
    return run(backfill=args.backfill)


if __name__ == "__main__":
    raise SystemExit(main())
