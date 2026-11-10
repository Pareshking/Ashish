"""Precompute tonight's ranking for the app, stamped with its contract.

Runs the SAME functions the app runs (src/engine/pipeline.build_engine and
rank_with_weights) on the SAME frames (src/loaders/price_source.load) with
the default weights, and writes data_cache/rankings.parquet with the contract
inside it (src/loaders/ranking_store). The nightly workflow uploads it to the
`data-latest` release; the app uses it only when every input matches, and
computes the ranking itself otherwise. A release asset is not git history, so
publishing it nightly does not grow the repository.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.core.config import DATA_DIR, DEFAULT_LOOKBACK_WEIGHTS, RANKINGS_SNAPSHOT_ASSET  # noqa: E402
from src.engine import pipeline  # noqa: E402
from src.engine.corporate_actions import adjust_ohlc, load_events  # noqa: E402
from src.loaders import price_source  # noqa: E402
from src.loaders.indices_loader import fetch_indices_data  # noqa: E402
from src.loaders.mcap_loader import fetch_market_caps  # noqa: E402
from src.loaders.ranking_store import contract, write_snapshot  # noqa: E402


def main() -> int:
    idx_info = fetch_indices_data([])
    symbols = idx_info["Symbol"].unique().tolist()
    src, _deep = price_source.load(symbols)
    if src is None:
        print("✗ the price store cannot serve a ranking frame")
        return 1
    for note in src.notes:
        print(f"  note: {note}")
    frames, applied = adjust_ohlc(
        {"adj_close": src.adj_close, "close": src.close, "high": src.high, "low": src.low},
        load_events())
    adj_close, close_p, high_p, low_p = frames["adj_close"], frames["close"], frames["high"], frames["low"]
    mcaps = fetch_market_caps(symbols)
    w = [float(x) for x in DEFAULT_LOOKBACK_WEIGHTS]
    weights = tuple(x / sum(w) for x in w)
    calc = pipeline.build_engine(adj_close, high_p, low_p, close_p, src.volume, idx_info, mcaps,
                                 corporate_actions=applied)
    _calc, rank_df = pipeline.rank_with_weights(calc, weights, idx_info, mcaps, close_p, high_p,
                                                intraday=src.intraday)
    if rank_df is None or rank_df.empty:
        print("✗ ranking came back empty; publishing nothing")
        return 1
    as_of = pipeline.ranking_as_of(adj_close)
    terms = contract(
        price_fingerprint=pipeline.price_fingerprint(adj_close),
        symbols_fingerprint=pipeline.symbols_fingerprint(symbols),
        weights=weights,
        pipeline_version=pipeline.PIPELINE_VERSION,
        universe=sorted(idx_info["Symbol"].unique().tolist()),
        price_as_of=as_of,
        price_source=src.source,
        applied_actions=applied,
    )
    out = os.path.join(DATA_DIR, RANKINGS_SNAPSHOT_ASSET)
    write_snapshot(out, rank_df, terms)
    print(f"✓ ranking precomputed: {len(rank_df)} rows as of {as_of} -> {out} "
          f"({os.path.getsize(out) / 1024**2:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
