"""Freeze closed months into the track record (data/track_record.json).

  python scripts/update_track_record.py            # monthly, after the 1st
  python scripts/update_track_record.py --dry-run

Runs the record's pinned configuration (track_record.TRACK_RECORD_CONFIG) from
inception through the latest settled session, then writes every CLOSED month
not already in the ledger. A stored month is never rewritten (``--force`` is a
deliberate, logged rebuild). Paresh's guard is kept: if today's replay
disagrees with a month already frozen by more than TOLERANCE, no new month is
frozen until someone looks.

Months struck more than 35 days after they began are marked "replayed":
they were not recorded at the time, and before the first membership snapshot
they were scored on today's list (survivorship).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.engine import systems  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.extra_universe import SYSTEM_750  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.engine.track_record import (  # noqa: E402
    TRACK_RECORD_CONFIG,
    calendar_month_returns,
    config_fingerprint_for_month,
    finalize_months,
    load_ledger,
    months_to_cover,
    save_ledger,
    summary_stats,
)
from src.loaders import benchmark_store, price_source  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402

TOLERANCE = 0.0005   # 0.05 percentage points


def replay(as_of_cut: str | None = None):
    syms = fetch_indices_data()["Symbol"].tolist()
    _frames, deep = price_source.load(syms)
    if deep is None:
        raise SystemExit("price store cannot reach the 12-month lookback")
    if as_of_cut:
        deep = deep.loc[:as_of_cut]
    start = systems.inception(SYSTEM_750)
    deep = deep.loc[deep.index >= (start - 24).start_time]
    as_of = pd.Timestamp(deep.index[-1])
    months = max(months_to_cover(as_of, start), 1)
    from src.core.config import BENCHMARK_SYMBOL
    bench = benchmark_store.history("max", BENCHMARK_SYMBOL).loc[:as_of]
    membership = systems.membership_for(SYSTEM_750)
    cfg = TRACK_RECORD_CONFIG
    result = run_backtest(
        f"trackrecord_us_{as_of:%Y%m%d}_{months}", deep,
        top_n=cfg["top_n"], rebal_freq=cfg["rebal_freq"], ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"], weight_method=cfg["weight_method"],
        config_weights=cfg["config_weights"], cost_bps=cfg["cost_bps"], buffer_n=cfg["buffer_n"],
        members_only_scoring_from=cfg.get("members_only_scoring_from"),
        ema_warmup_from=cfg.get("ema_warmup_from"), hold_cap=cfg.get("hold_cap"),
        hold_cap_from=cfg.get("hold_cap_from"), buy_size=cfg.get("buy_size"),
        weight_reset_months=tuple(cfg.get("weight_reset_months") or ()) or None,
        stock_cap=cfg["stock_cap"], sector_cap=cfg["sector_cap"],
        sector_map=record_sector_map(deep.columns), _benchmark_close=bench,
        backtest_months=months, _membership=membership, stateful_history=True,
        history_start=start.start_time,
    )
    return result, as_of


def drift(ledger: dict, curve: pd.Series) -> list[str]:
    """Frozen months the replay now disagrees with, beyond TOLERANCE."""
    fresh = calendar_month_returns(curve)
    out = []
    for key, row in (ledger.get("months") or {}).items():
        p = pd.Period(key, freq="M")
        if p in fresh.index and abs(float(fresh.loc[p]) - float(row["strategy"])) > TOLERANCE:
            out.append(f"{key}: stored {row['strategy']:+.4%}, replay {float(fresh.loc[p]):+.4%}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)

    start = systems.inception(SYSTEM_750)
    path = systems.ledger_path(SYSTEM_750)
    result, as_of = replay()
    if not result:
        print("✗ the replay produced nothing")
        return 1
    stats = result["stats"]
    pit_from = stats.get("pit_from")
    ledger = load_ledger(path, start)
    bad = drift(ledger, result["equity_curve"])
    for b in bad:
        print(f"  ! drift {b} -- stored value stands")

    def fingerprint(period):
        return config_fingerprint_for_month(TRACK_RECORD_CONFIG, period)

    before = dict(ledger.get("months") or {})
    ledger, added, skipped = finalize_months(
        ledger, result["equity_curve"], result["benchmark"], fingerprint=fingerprint,
        as_of=as_of, data_as_of=as_of, pit_from=pit_from, force=args.force)
    if bad and added and not args.force:
        print(f"✗ refusing to freeze {', '.join(added)} while frozen months drift")
        return 1

    struck = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for key in added:
        m = ledger["months"][key]
        m["struck_on"] = struck
        # Struck more than 35 days after the month began: its book was not
        # formed live, it was replayed (Jan-Oct 2026, struck 10 Nov 2026).
        if pd.Timestamp(struck) - pd.Period(key, freq="M").start_time > pd.Timedelta(days=35):
            m["replayed"] = True
    if args.force and added:
        ledger.setdefault("rebuilds", []).append({
            "on": struck, "months": added, "note": args.note,
            "previous_values": {k: before[k]["strategy"] for k in added if k in before}})
    ledger["price_basis"] = TRACK_RECORD_CONFIG["prices"]
    print(f"→ as of {as_of:%Y-%m-%d}: {len(before)} months on file, {len(added)} added, {len(skipped)} kept")
    for key in added:
        e = ledger["months"][key]
        b = e.get("benchmark")
        print(f"  + {key}  strategy {e['strategy']:+.2%}"
              + (f"  benchmark {b:+.2%}  alpha {e['alpha']:+.2%}" if b is not None else "")
              + ("  (replayed)" if e.get("replayed") else ""))
    if args.dry_run:
        print("→ dry run; nothing written")
        return 0
    if not added and not args.force:
        print("→ no new closed months; file untouched")
        return 0
    save_ledger(ledger, path)
    s = summary_stats(ledger)
    print(f"✓ wrote {path}: {s['months']} months, {s['first']} → {s['last']}, total {s['total_return']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
