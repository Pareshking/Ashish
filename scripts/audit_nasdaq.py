"""Cross-check stored closes against Nasdaq.com's official closes.

Nasdaq.com serves each stock's official close (the primary listing exchange's
closing print, split-adjusted) for about ten years, one request per symbol,
for NYSE- as well as Nasdaq-listed stocks. It is an independent source for the
CLOSE: it does not share Yahoo's pipeline.

  python scripts/audit_nasdaq.py --sample 150          # random sample
  python scripts/audit_nasdaq.py --symbols AAPL MSFT   # named symbols

Writes ``reports/nasdaq_audit_<date>.csv`` (one row per symbol) and prints a
summary. Exit 1 when the share of compared closes within TOLERANCE falls below
PASS_SHARE, so a scheduled run alerts.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core import market_time as mt  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402

URL = "https://api.nasdaq.com/api/quote/{sym}/historical"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
           "Accept": "application/json"}
TOLERANCE = 0.005        # 0.5% of the close
PASS_SHARE = 0.995       # of all compared (symbol, date) pairs
DELAY_S = 1.0


def nasdaq_history(sym: str, start: str, end: str, session=None) -> pd.Series:
    """Official closes from ``start``. The API returns no rows at all when
    ``end`` is in the past (probed 10 Nov 2026), so ``end`` should be today."""
    s = session or requests.Session()
    r = s.get(URL.format(sym=sym.replace("-", ".")), headers=HEADERS, timeout=30,
              params={"assetclass": "stocks", "fromdate": start, "todate": end, "limit": 9999})
    r.raise_for_status()
    data = (r.json() or {}).get("data") or {}
    rows = ((data.get("tradesTable") or {}).get("rows")) or []
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    out = pd.Series(df["close"].str.replace(r"[$,]", "", regex=True).astype(float).values,
                    index=pd.to_datetime(df["date"], format="%m/%d/%Y"), name=sym)
    return out.sort_index()


def compare(stored: pd.Series, official: pd.Series) -> dict:
    j = pd.concat([stored.rename("ours"), official.rename("nasdaq")], axis=1, join="inner").dropna()
    if j.empty:
        return {"compared": 0, "within": 0, "worst_date": "", "worst_pct": float("nan"), "ours_only": len(stored), "nasdaq_only": len(official)}
    d = (j["ours"] / j["nasdaq"] - 1).abs()
    w = d.idxmax()
    return {
        "compared": int(len(j)),
        "within": int((d <= TOLERANCE).sum()),
        "worst_date": str(w.date()),
        "worst_pct": round(float(d.loc[w]) * 100, 3),
        "ours_only": int(len(stored.index.difference(official.index))),
        "nasdaq_only": int(len(official.index.difference(stored.index))),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", type=int, default=150)
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--seed", type=int, default=None, help="default: today's date, so a daily run rotates")
    args = ap.parse_args(argv)

    today = mt.ny_today()
    start = str(today.replace(year=today.year - 10))
    long = ps.read_long(start=start)
    close = ps.wide(long, "Close")
    syms = args.symbols or sorted(close.columns)
    if not args.symbols:
        random.Random(args.seed if args.seed is not None else int(today.strftime("%Y%m%d"))).shuffle(syms)
        syms = syms[: args.sample]

    s = requests.Session()
    rows = []
    for i, sym in enumerate(syms):
        try:
            off = nasdaq_history(sym, start, str(today), s)
            res = compare(close[sym].dropna() if sym in close else pd.Series(dtype=float), off)
            res["error"] = "" if len(off) else "no rows"
        except Exception as exc:  # noqa: BLE001
            res = {"compared": 0, "within": 0, "error": f"{type(exc).__name__}"}
        res["symbol"] = sym
        rows.append(res)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(syms)}", flush=True)
        time.sleep(DELAY_S)

    rep = pd.DataFrame(rows).set_index("symbol")
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    out = os.path.join(ROOT, "reports", f"nasdaq_audit_{today}.csv")
    rep.to_csv(out)
    n, w = int(rep["compared"].sum()), int(rep["within"].sum())
    share = w / n if n else 0.0
    bad = rep[(rep["compared"] > 0) & (rep["within"] < rep["compared"])].sort_values("worst_pct", ascending=False)
    print(f"Nasdaq cross-check {today}: {len(rep)} symbols, {n:,} closes compared, "
          f"{share:.4%} within {TOLERANCE:.1%}; {int((rep['error'] != '').sum())} symbols not served")
    if len(bad):
        print("symbols with closes outside tolerance (worst first):")
        print(bad.head(30).to_string())
    print(f"report: {out}")
    return 0 if share >= PASS_SHARE else 1


if __name__ == "__main__":
    raise SystemExit(main())
