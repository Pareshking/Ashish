"""Build or carry forward data/all_time_highs.csv.

  python scripts/build_ath.py --full   # Yahoo's whole history (once, ~6 min)
  python scripts/build_ath.py          # nightly: max(file, store highs)
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.loaders import ath_loader  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402


def from_store() -> pd.DataFrame:
    long = ps.read_long()
    i = long.groupby("Symbol")["High"].idxmax()
    best = long.loc[i, ["Symbol", "High", "Date"]].rename(columns={"High": "ATH", "Date": "ATHDate"})
    best["AsOf"] = long["Date"].max()
    return best.reset_index(drop=True)


def from_yahoo_full(symbols: list[str]) -> pd.DataFrame:
    from scripts.sync_prices import CHUNK, _download

    rows = []
    for i in range(0, len(symbols), CHUNK):
        raw = _download(symbols[i:i + CHUNK], None)
        hi = raw["High"]
        for s in hi.columns:
            h = hi[s].dropna()
            if len(h):
                rows.append((s, float(h.max()), h.idxmax()))
        print(f"  {min(i + CHUNK, len(symbols))}/{len(symbols)}", flush=True)
    return pd.DataFrame(rows, columns=["Symbol", "ATH", "ATHDate"])


def combine(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    both = pd.concat([a[["Symbol", "ATH", "ATHDate"]], b[["Symbol", "ATH", "ATHDate"]]], ignore_index=True)
    both["ATHDate"] = pd.to_datetime(both["ATHDate"]).dt.tz_localize(None)
    both = both.sort_values(["Symbol", "ATH", "ATHDate"]).groupby("Symbol").tail(1)
    return both.reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args(argv)
    store = from_store()
    syms = sorted(pd.read_csv(os.path.join(ROOT, "data", "universe.csv"))["Yahoo"])
    base = from_yahoo_full(syms) if args.full else ath_loader.load_ath_snapshot()
    out = combine(base, store) if len(base) else store
    out = out[out["Symbol"].isin(syms)].sort_values("Symbol")
    out["AsOf"] = pd.Timestamp(store["AsOf"].max()).date().isoformat()
    out["ATH"] = out["ATH"].round(4)
    out["ATHDate"] = pd.to_datetime(out["ATHDate"]).dt.strftime("%Y-%m-%d")
    out.to_csv(ath_loader.FILE, index=False)
    print(f"all-time highs: {len(out)} symbols as of {out['AsOf'].iloc[0]}; "
          f"{(pd.to_datetime(out['ATHDate']) < '2008-01-01').sum()} set before 2008")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
