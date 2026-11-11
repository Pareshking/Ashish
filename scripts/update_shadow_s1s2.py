"""Forward shadow of S1 + S2 beside the live book (owner, 10 Nov 2026).

    python scripts/update_shadow_s1s2.py

S1 (residual momentum, Blitz, Huij & Martens 2011; docs/MOMENTUM_PREREG.md)
changes which stocks are held, so unlike the S2 shadow this one needs its own
book: the record's pinned configuration (track_record.TRACK_RECORD_CONFIG,
every forward-dated rule included) replayed from inception with S1's score
(0.75 x the live score's z + 0.25 x the residual z, French three factors over
36 months to m-1). Each closed month is then scaled by S2's weight
(scripts/update_shadow_s2.weight), the rest in SPY with dividends:

    shadow = w * s1_book + (1 - w) * benchmark - cost_bps * |w - w_prev|

Recorded, never traded. In 2020-2026 the S1 + S2 family led stage 2 of the
study only in hindsight (docs/MOMENTUM_PREREG.md, stage 2): the selection rule
did not choose it, so only months after 10 Nov 2026 count as evidence. Months
before that are marked "replayed".
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("FRENCH_DIR", os.path.join(ROOT, ".cache", "french"))

from scripts import research_prereg as rp  # noqa: E402
from scripts import update_shadow_s2 as s2  # noqa: E402
from src.engine import systems  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.extra_universe import SYSTEM_750  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG, calendar_month_returns, months_to_cover  # noqa: E402
from src.loaders import benchmark_store, price_source  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402

RECORD = os.path.join(ROOT, "data", "track_record.json")
OUT = os.path.join(ROOT, "data", "shadow_s1s2.json")
LIVE_FROM = "2026-11"            # first month that counts as forward evidence


def s1_book() -> pd.Series:
    syms = fetch_indices_data()["Symbol"].tolist()
    _frames, deep_full = price_source.load(syms)
    fr = rp.load_french()
    res = rp.residual_scores(deep_full, fr["ff3_m"])
    start = systems.inception(SYSTEM_750)
    deep = deep_full.loc[deep_full.index >= (start - 24).start_time]
    as_of = pd.Timestamp(deep.index[-1])
    months = max(months_to_cover(as_of, start), 1)
    from src.core.config import BENCHMARK_SYMBOL
    bench = benchmark_store.history("max", BENCHMARK_SYMBOL).loc[:as_of]
    cfg = TRACK_RECORD_CONFIG
    result = run_backtest(
        f"shadow_s1s2_{as_of:%Y%m%d}_{months}", deep,
        top_n=cfg["top_n"], rebal_freq=cfg["rebal_freq"], ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"], weight_method=cfg["weight_method"],
        config_weights=cfg["config_weights"], cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"],
        members_only_scoring_from=cfg.get("members_only_scoring_from"),
        ema_warmup_from=cfg.get("ema_warmup_from"), hold_cap=cfg.get("hold_cap"),
        hold_cap_from=cfg.get("hold_cap_from"), buy_size=cfg.get("buy_size"),
        weight_reset_months=tuple(cfg.get("weight_reset_months") or ()) or None,
        stock_cap=cfg["stock_cap"], sector_cap=cfg["sector_cap"],
        sector_map=record_sector_map(deep.columns), _benchmark_close=bench,
        backtest_months=months, _membership=systems.membership_for(SYSTEM_750), stateful_history=True,
        history_start=start.start_time, research_label="S1", _research_score=rp.s1_score_fn(res),
    )
    return calendar_month_returns(result["equity_curve"])


def main() -> int:
    logging.disable(logging.WARNING)
    rec = json.load(open(RECORD))
    book = s1_book()
    umd, vintage = s2.umd_daily(os.environ["FRENCH_DIR"])
    old = json.load(open(OUT)) if os.path.exists(OUT) else {"months": {}, "log": []}
    out = {"description": "S1 + S2 forward shadow (docs/MOMENTUM_PREREG.md): recorded, not traded",
           "rule": "the record's configuration with S1's score; the book scaled by S2's weight, rest SPY with "
                   "dividends; 10 bps on |dw|", "live_from": LIVE_FROM, "months": {},
           "log": list(old.get("log") or [])}
    struck = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    w_prev = None
    for key in sorted(rec["months"]):
        p = pd.Period(key, "M")
        if p not in book.index:
            print(f"✗ the S1 replay has no {key}")
            return 1
        w, note = s2.weight(umd, p - 1)
        cost = (1 - w) * s2.COST_BPS / 2e4 if w_prev is None else abs(w - w_prev) * s2.COST_BPS / 1e4
        b = float(book.loc[p])
        bench = rec["months"][key]["benchmark"]
        row = {"weight": round(w, 4), "s1_book": round(b, 6), "live_book": rec["months"][key]["strategy"],
               "benchmark": bench, "shadow": round(w * b + (1 - w) * bench - cost, 6),
               "french_vintage": vintage, "note": note, "replayed": key < LIVE_FROM}
        prev = (old.get("months") or {}).get(key)
        if prev and abs(prev.get("shadow", 0) - row["shadow"]) > 5e-4:
            out["log"].append({"on": struck, "month": key, "previous_shadow": prev["shadow"],
                               "new_shadow": row["shadow"], "reason": "replay changed"})
        row["recorded_on"] = prev.get("recorded_on", struck) if prev else struck
        out["months"][key] = row
        w_prev = w
    tot = lambda f: math.prod(1 + r[f] for r in out["months"].values()) - 1  # noqa: E731
    out["totals"] = {k: round(tot(k), 6) for k in ("live_book", "s1_book", "shadow", "benchmark")}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    for k, r in out["months"].items():
        print(f"  {k}  w {r['weight']:.2f}  live {r['live_book']:+.2%}  S1 {r['s1_book']:+.2%}  "
              f"shadow {r['shadow']:+.2%}")
    t = out["totals"]
    print(f"✓ {OUT}: live {t['live_book']:+.2%}, S1 book {t['s1_book']:+.2%}, "
          f"S1+S2 {t['shadow']:+.2%}, S&P 500 {t['benchmark']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
