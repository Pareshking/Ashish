"""Forward shadow of S2 beside the live book (owner, 10 Nov 2026).

    python scripts/update_shadow_s2.py [--french-cache DIR]

S2 (docs/MOMENTUM_PREREG.md, Barroso & Santa-Clara 2015) was the one
pre-registered test that passed: the book scaled by
w = min(1, 12% / sigma), sigma the annualised realised volatility of Kenneth
French's daily US momentum factor (UMD) over the 126 sessions ending at the
last session of the month BEFORE the signal month (French publishes with a
lag; if that month is not yet published, the latest published month is used
and logged), the rest in SPY with dividends.

The shadow is recorded, never traded. Each month of data/track_record.json
gives the shadow month:

    shadow = w * strategy + (1 - w) * benchmark - cost_bps * |w - w_prev|

(first month: half a round trip on the SPY sleeve, as the engine charges to
open a book). Monthly re-mixing is an approximation: the study let the two
sleeves drift day by day between fills. Months already in data/shadow_s2.json
are not rewritten unless the record's month changed (then the change is logged).
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

RECORD = os.path.join(ROOT, "data", "track_record.json")
OUT = os.path.join(ROOT, "data", "shadow_s2.json")
URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"
TARGET, WINDOW, COST_BPS = 0.12, 126, 10.0


def umd_daily(cache: str | None) -> tuple[pd.Series, str]:
    path = os.path.join(cache, "F-F_Momentum_Factor_daily_CSV.zip") if cache else None
    if path and os.path.exists(path):
        raw = open(path, "rb").read()
    else:
        raw = urllib.request.urlopen(URL, timeout=60).read()
        if path:
            os.makedirs(cache, exist_ok=True)
            open(path, "wb").write(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    rows, vintage = [], ""
    for line in text.splitlines():
        if "CRSP" in line and not vintage:
            vintage = "".join(ch for ch in line.split("CRSP")[0] if ch.isdigit())[-6:]
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 2 and len(p[0]) == 8 and p[0].isdigit():
            rows.append((pd.Timestamp(p[0]), float(p[1]) / 100.0))
    s = pd.Series(dict(rows)).sort_index()
    return s, vintage


def weight(umd: pd.Series, month: pd.Period) -> tuple[float, str]:
    """S2's weight for a book whose signal falls in ``month``: UMD to the end of month-1."""
    want = month - 1
    have = umd[umd.index.to_period("M") <= want]
    used = have.index[-1].to_period("M") if len(have) else None
    if used is None or len(have) < WINDOW:
        return float("nan"), "no data"
    u = have.iloc[-WINDOW:].to_numpy()
    sigma = math.sqrt(252 * float((u * u).mean()))
    note = "" if used == want else f"French not yet published for {want}; used {used}"
    return min(1.0, TARGET / sigma), note


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--french-cache")
    args = ap.parse_args(argv)
    rec = json.load(open(RECORD))
    umd, vintage = umd_daily(args.french_cache)
    old = json.load(open(OUT)) if os.path.exists(OUT) else {"months": {}, "log": []}
    out = {"description": "S2 forward shadow (docs/MOMENTUM_PREREG.md): recorded, not traded",
           "rule": f"w = min(1, {TARGET:.0%} / UMD {WINDOW}-session realised vol to month m-1); rest SPY with dividends; "
                   f"{COST_BPS:g} bps on |dw|", "months": {}, "log": list(old.get("log") or [])}
    w_prev = None
    struck = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for key in sorted(rec["months"]):
        m = rec["months"][key]
        signal_month = pd.Period(key, "M") - 1          # the book of month k is signalled at the end of k-1
        w, note = weight(umd, signal_month)
        if not math.isfinite(w):
            print(f"✗ no weight for {key}")
            return 1
        cost = (1 - w) * COST_BPS / 2e4 if w_prev is None else abs(w - w_prev) * COST_BPS / 1e4
        row = {"weight": round(w, 4), "strategy": m["strategy"], "benchmark": m["benchmark"],
               "shadow": round(w * m["strategy"] + (1 - w) * m["benchmark"] - cost, 6),
               "french_vintage": vintage, "note": note}
        prev = (old.get("months") or {}).get(key)
        if prev and prev.get("strategy") != row["strategy"]:
            out["log"].append({"on": struck, "month": key, "previous_shadow": prev.get("shadow"),
                               "reason": "the record's month changed (re-strike)"})
        row["recorded_on"] = prev.get("recorded_on", struck) if prev else struck
        out["months"][key] = row
        w_prev = w
    tot = lambda f: math.prod(1 + r[f] for r in out["months"].values()) - 1  # noqa: E731
    out["totals"] = {"strategy": round(tot("strategy"), 6), "shadow": round(tot("shadow"), 6),
                     "benchmark": round(tot("benchmark"), 6)}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    for k, r in out["months"].items():
        print(f"  {k}  w {r['weight']:.2f}  book {r['strategy']:+.2%}  shadow {r['shadow']:+.2%}  {r['note']}")
    t = out["totals"]
    print(f"✓ {OUT}: book {t['strategy']:+.2%}, shadow {t['shadow']:+.2%}, S&P 500 {t['benchmark']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
