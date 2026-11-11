"""Forward shadow of F2, the size-weighted book, beside the live book (owner, 11 Nov 2026).

    python scripts/update_shadow_f2.py

F2 (docs/MOMENTUM_PREREG.md, stage 3): the record's pinned configuration
(track_record.TRACK_RECORD_CONFIG, every forward-dated rule included, so from
the 30 Nov 2026 signal its holdings drift, winners run to 15% and weights reset
in March and September as the live book's do), with each holding's target
weight in proportion to its 63-session mean traded value (split-adjusted close
x volume) instead of equal, stock cap 15%, sector cap 40%.

Recorded, never traded. Stage 3's verdict was inconclusive (ahead on every
check but turnover). Months before Nov 2026 are replays and marked so; only
later months count as evidence.
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

from scripts.research_prereg import traded_value  # noqa: E402
from src.engine import systems  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.extra_universe import SYSTEM_750  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG, calendar_month_returns, months_to_cover  # noqa: E402
from src.loaders import benchmark_store, price_source  # noqa: E402
from src.loaders import price_store as ps  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402

RECORD = os.path.join(ROOT, "data", "track_record.json")
OUT = os.path.join(ROOT, "data", "shadow_f2.json")
LIVE_FROM = "2026-11"


def f2_book() -> pd.Series:
    syms = fetch_indices_data()["Symbol"].tolist()
    _frames, deep = price_source.load(syms)
    start = systems.inception(SYSTEM_750)
    deep = deep.loc[deep.index >= (start - 24).start_time]
    w = ps.read_wide(["Close", "Volume"], start=str(deep.index[0].date()), symbols=list(deep.columns))
    size = traded_value(w["Close"].reindex(index=deep.index, columns=deep.columns),
                        w["Volume"].reindex(index=deep.index, columns=deep.columns))
    as_of = pd.Timestamp(deep.index[-1])
    months = max(months_to_cover(as_of, start), 1)
    from src.core.config import BENCHMARK_SYMBOL
    bench = benchmark_store.history("max", BENCHMARK_SYMBOL).loc[:as_of]
    cfg = TRACK_RECORD_CONFIG
    result = run_backtest(
        f"shadow_f2_{as_of:%Y%m%d}_{months}", deep,
        top_n=cfg["top_n"], rebal_freq=cfg["rebal_freq"], ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"], weight_method="Traded Value", _research_size=size,
        config_weights=cfg["config_weights"], cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"],
        members_only_scoring_from=cfg.get("members_only_scoring_from"),
        ema_warmup_from=cfg.get("ema_warmup_from"), hold_cap=cfg.get("hold_cap"),
        hold_cap_from=cfg.get("hold_cap_from"), buy_size=cfg.get("buy_size"),
        weight_reset_months=tuple(cfg.get("weight_reset_months") or ()) or None,
        stock_cap=0.15, sector_cap=cfg["sector_cap"],
        sector_map=record_sector_map(deep.columns), _benchmark_close=bench,
        backtest_months=months, _membership=systems.membership_for(SYSTEM_750), stateful_history=True,
        history_start=start.start_time, research_label="F2",
    )
    return calendar_month_returns(result["equity_curve"])


def main() -> int:
    logging.disable(logging.WARNING)
    rec = json.load(open(RECORD))
    book = f2_book()
    old = json.load(open(OUT)) if os.path.exists(OUT) else {"months": {}, "log": []}
    out = {"description": "F2 forward shadow (docs/MOMENTUM_PREREG.md stage 3): recorded, not traded",
           "rule": "the record's configuration with traded-value target weights (63 sessions), stock cap 15%",
           "live_from": LIVE_FROM, "months": {}, "log": list(old.get("log") or [])}
    struck = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for key in sorted(rec["months"]):
        p = pd.Period(key, "M")
        if p not in book.index:
            print(f"✗ the F2 replay has no {key}")
            return 1
        row = {"f2_book": round(float(book.loc[p]), 6), "live_book": rec["months"][key]["strategy"],
               "benchmark": rec["months"][key]["benchmark"], "replayed": key < LIVE_FROM}
        prev = (old.get("months") or {}).get(key)
        if prev and abs(prev.get("f2_book", 0) - row["f2_book"]) > 5e-4:
            out["log"].append({"on": struck, "month": key, "previous": prev["f2_book"],
                               "new": row["f2_book"], "reason": "replay changed"})
        row["recorded_on"] = prev.get("recorded_on", struck) if prev else struck
        out["months"][key] = row
    tot = lambda f: math.prod(1 + r[f] for r in out["months"].values()) - 1  # noqa: E731
    out["totals"] = {k: round(tot(k), 6) for k in ("live_book", "f2_book", "benchmark")}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    for k, r in out["months"].items():
        print(f"  {k}  live {r['live_book']:+.2%}  F2 {r['f2_book']:+.2%}  S&P 500 {r['benchmark']:+.2%}")
    t = out["totals"]
    print(f"✓ {OUT}: live {t['live_book']:+.2%}, F2 {t['f2_book']:+.2%}, S&P 500 {t['benchmark']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
