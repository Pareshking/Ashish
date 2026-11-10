"""Rebuild data/momentum_health.csv: momentum's monthly spread from our ranking.

    python scripts/build_momentum_health.py [--check-french]

Each month-end since 2010 the S&P 1500's members are ranked by the site's
composite score on the store's dividend-adjusted closes; the next month's
top-fifth minus bottom-fifth return is that month's spread
(src/engine/momentum_health.py), beside the record configuration's own monthly
returns (src/engine/portfolio_history.py).

SURVIVORSHIP, stated: membership history begins 10 Nov 2026, so every month is
scored on TODAY's list (Paresh's version refuses months before its point-in-
time history; the US has none). Delisted losers are missing from the bottom
fifth, which tends to make the spread look smaller than it was. --check-french
measures it against Kenneth French's US momentum factor (UMD, built on CRSP,
survivorship-free) and writes the result to data/momentum_health_check.json for
the Dashboard.

Refuses to write (exit 1) when there are fewer than 24 months, the newest is
more than two months old, a month scored fewer than 100 stocks, or a spread is
not a number.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "momentum_health.csv"
LATEST = ROOT / "data" / "momentum_health_latest.json"
CHECK = ROOT / "data" / "momentum_health_check.json"
UMD_FILE = ROOT / "data" / "french_umd.csv"
FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip"
START = "2010-01-01"


def _close() -> pd.DataFrame:
    from src.loaders import nse_long

    loaded = nse_long.load(with_value=False)
    if loaded is None:
        raise SystemExit("::error::the price store could not be read")
    close = loaded[0]
    return close.loc[close.index >= pd.Timestamp(START) - pd.DateOffset(months=14)].astype("float64")


def build() -> pd.DataFrame:
    from src.engine.momentum_health import monthly_spreads

    close = _close()
    sp = monthly_spreads(close, None, first_month=pd.Period(START, freq="M"))
    try:
        from src.engine.portfolio_history import portfolio_months
        from src.loaders import benchmark_store

        bench = benchmark_store.history("max", "SPTM_TR")
        sp = sp.merge(portfolio_months(close, bench, "sp1500"), on="month", how="left")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::portfolio months not written: {type(exc).__name__}: {exc}")
    return sp


def build_latest() -> dict | None:
    from src.engine.momentum_health import latest_qualified

    return latest_qualified(_close(), None, first_month=pd.Period(START, freq="M"))


def french_umd() -> pd.Series:
    """Monthly UMD in percent, indexed by 'YYYY-MM'."""
    import requests

    r = requests.get(FRENCH_URL, timeout=60, headers={"User-Agent": "us-momentum-terminal/1.0"})
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("latin-1")
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0].isdigit():
            rows.append((f"{parts[0][:4]}-{parts[0][4:]}", float(parts[1])))
        elif rows and len(parts[0]) == 4 and parts[0].isdigit():
            break   # the annual table follows the monthly one
    return pd.Series(dict(rows), name="UMD")


def check_french(sp: pd.DataFrame) -> dict:
    umd = french_umd()
    keep = umd[umd.index >= START[:7]]
    keep.rename_axis("month").reset_index().to_csv(UMD_FILE, index=False)
    m = sp.set_index("month")[["spread"]].join(umd, how="inner").dropna()
    r12 = m.rolling(12).sum().dropna()
    out = {
        "months": int(len(m)), "first": str(m.index[0]), "last": str(m.index[-1]),
        "corr_monthly": round(float(m["spread"].corr(m["UMD"])), 3),
        "corr_12m": round(float(r12["spread"].corr(r12["UMD"])), 3),
        "same_sign": round(float((np.sign(m["spread"]) == np.sign(m["UMD"])).mean()), 3),
        "mean_spread": round(float(m["spread"].mean()), 3), "mean_umd": round(float(m["UMD"].mean()), 3),
        "source": FRENCH_URL,
    }
    return out


def problems(sp: pd.DataFrame, today: pd.Timestamp) -> list[str]:
    out = []
    if len(sp) < 24:
        return [f"only {len(sp)} months"]
    newest = pd.Period(sp["month"].iloc[-1], freq="M")
    if (pd.Period(today, freq="M") - newest).n > 2:
        out.append(f"newest month {newest} is more than two months old")
    if (sp["n"] < 100).any():
        out.append("a month has fewer than 100 stocks scored")
    if not np.isfinite(sp["spread"].to_numpy(dtype=float)).all():
        out.append("a spread is not a number")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check-french", action="store_true")
    args = ap.parse_args()
    sp = build()
    bad = problems(sp, pd.Timestamp.today())
    for b in bad:
        print(f"::error::{b}")
    if bad:
        return 1
    out = sp.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.round({c: 4 for c in ("top", "bottom", "spread", "qualified", "portfolio", "bench_tr", "ew", "top50", "d2")}).to_csv(OUT, index=False)
    print(f"{len(out)} months {out['month'].iloc[0]}..{out['month'].iloc[-1]} -> {OUT}")
    if args.check_french:
        try:
            c = check_french(sp)
            CHECK.write_text(json.dumps(c, indent=1) + "\n", encoding="utf-8")
            print(f"French UMD: {c['months']} months {c['first']}..{c['last']}, correlation "
                  f"{c['corr_monthly']} monthly, {c['corr_12m']} over 12 months, same sign {c['same_sign']:.0%}; "
                  f"mean spread {c['mean_spread']}% vs UMD {c['mean_umd']}% a month")
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::French check not run: {type(exc).__name__}: {exc}")
    try:
        latest = build_latest()
        if latest:
            LATEST.write_text(json.dumps(latest, indent=1) + "\n", encoding="utf-8")
            print(f"latest qualified {latest['qualified']:.1%} at {latest['date']}")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::latest qualified share not written: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
