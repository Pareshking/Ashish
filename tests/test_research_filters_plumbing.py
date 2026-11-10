"""Research filters in run_backtest are off by default and change nothing then.

Owner, 10 Nov 2026: additional momentum filters for research, on top of the
live score. With the defaults the live record, Actions, Portfolio and the
ranking must be byte-identical. Two proofs:

* GOLDEN: a synthetic run with the record's rules (caps, buffer, hold cap,
  six-monthly reset) hashes to the value the engine gave BEFORE the research
  keywords existed (commit 715782d). Also checked once on the real store,
  2020-01 to 2026-10, before the commit: equity curve, tradebook, live book,
  month changes and stats identical (docs/RESEARCH_FILTERS.md).
* NEUTRAL PATHS: a gate that passes everyone, a 0% drop and a one-name pool
  run every new line and must give the default run to the bit.
"""

import hashlib
import warnings

import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import run_backtest

_RUN = run_backtest
while hasattr(_RUN, "__wrapped__"):
    _RUN = _RUN.__wrapped__

GOLDEN = "828390ce4060989814ff45ede0eeac85668566764f12219595d400e0eb27c5f9"


def _prices(n_days=760, n=60, seed=11):
    idx = pd.bdate_range("2021-01-04", periods=n_days)
    rng = np.random.default_rng(seed)
    lr = rng.normal(rng.normal(0.0004, 0.0008, n), rng.uniform(0.008, 0.03, n), (n_days, n))
    return pd.DataFrame(100 * np.exp(np.cumsum(lr, axis=0)), index=idx,
                        columns=[f"S{i:02d}" for i in range(n)])


def _run(**kw):
    p = _prices()
    sec = {c: f"G{i % 4}" for i, c in enumerate(p.columns)}
    return _RUN("golden", p, top_n=10, buffer_n=20, cost_bps=10.0, sector_map=sec,
                _benchmark_close=p.mean(axis=1), backtest_months=14, stateful_history=True,
                hold_cap=0.15, hold_cap_from="2023-06-30", buy_size=0.05,
                weight_reset_months=(3, 9), **kw)


def _digest(res):
    h = hashlib.sha256()
    for k in ("equity_curve", "equity_gross", "benchmark"):
        h.update(np.round(res[k].to_numpy(dtype=float), 12).tobytes())
        h.update(str(list(res[k].index)).encode())
    for k in ("monthly", "tradebook", "closed_trades", "live_book", "month_changes"):
        v = res[k]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")    # round() on date columns: a no-op, as it should be
            h.update(v.round(10).to_csv().encode() if hasattr(v, "to_csv") else repr(v).encode())
    st = {k: (round(v, 10) if isinstance(v, float) else v) for k, v in res["stats"].items()}
    h.update(repr(sorted(st.items(), key=lambda x: x[0])).encode())
    return h.hexdigest()


def _same(a, b):
    for k in ("equity_curve", "equity_gross", "benchmark"):
        assert a[k].index.equals(b[k].index)
        assert a[k].to_numpy().tobytes() == b[k].to_numpy().tobytes(), k
    for k in ("monthly", "tradebook", "closed_trades", "live_book", "month_changes"):
        pd.testing.assert_frame_equal(a[k], b[k], check_exact=True)
    assert repr(a["stats"]) == repr(b["stats"])


def test_the_defaults_reproduce_the_engine_before_the_research_keywords():
    res = _run()
    assert len(res["tradebook"]) > 50          # a real run, not an empty one
    assert _digest(res) == GOLDEN


def test_neutral_research_paths_change_nothing_to_the_bit():
    base = _run()
    p = _prices()
    everyone = pd.DataFrame(True, index=p.index, columns=p.columns)
    values = pd.DataFrame(np.random.default_rng(3).normal(size=p.shape), index=p.index,
                          columns=p.columns)
    for kw in (
        dict(_research_gate=everyone, research_gate_on="both"),
        dict(_research_gate=pd.Series(True, index=p.index), research_gate_on="buy"),
        dict(_research_values=values, research_drop=0.0, research_gate_on="both"),
        dict(_research_values=values, research_pool=1),
    ):
        _same(base, _run(research_label="neutral", **kw))


def test_a_market_gate_that_is_always_off_holds_cash_on_both_and_buys_nothing_on_buy():
    p = _prices()
    off = pd.Series(False, index=p.index)
    cash = _run(research_label="off-both", _research_gate=off, research_gate_on="both")
    assert (cash["monthly"]["Holdings"] == 0).all()
    assert np.allclose(cash["equity_curve"].to_numpy(), 1.0)
    frozen = _run(research_label="off-buy", _research_gate=off, research_gate_on="buy")
    # Nothing was ever bought, so nothing is held either.
    assert (frozen["monthly"]["Holdings"] == 0).all()


def test_a_stock_gate_keeps_the_excluded_name_out_of_every_book():
    base = _run()
    held = base["tradebook"]["Symbol"].value_counts().index[0]
    p = _prices()
    gate = pd.DataFrame(True, index=p.index, columns=p.columns)
    gate[held] = False
    res = _run(research_label=f"no-{held}", _research_gate=gate, research_gate_on="both")
    assert held not in set(res["tradebook"]["Symbol"])
    assert held not in set(res["live_book"].get("Symbol", pd.Series(dtype=str)))


def test_a_buy_gate_still_keeps_a_holding_bought_before_it_closed():
    """Gate "buy": a name already held is judged on the live rules alone."""
    base = _run()
    tb = base["tradebook"]
    first = tb[tb["Action"].str.contains("BUY")].iloc[0]
    sym, start = first["Symbol"], pd.Timestamp(first["Period Start"])
    p = _prices()
    gate = pd.DataFrame(True, index=p.index, columns=p.columns)
    gate.loc[gate.index > start, sym] = False
    buy = _run(research_label="buy-gate", _research_gate=gate, research_gate_on="buy")
    both = _run(research_label="both-gate", _research_gate=gate, research_gate_on="both")
    held_after = lambda r: set(r["tradebook"].loc[  # noqa: E731
        r["tradebook"]["Action"].str.contains("HOLD"), "Symbol"])
    assert sym in held_after(base)
    assert sym in held_after(buy)
    assert sym not in held_after(both)


def test_the_pool_takes_new_buys_by_the_values_among_the_leaders():
    p = _prices()
    # Prefer the alphabetically last names: with a pool as wide as the
    # qualified list, the first book is those names among the qualified.
    pref = pd.DataFrame(np.tile(np.arange(p.shape[1], dtype=float), (len(p), 1)),
                        index=p.index, columns=p.columns)
    res = _run(research_label="pool", _research_values=pref, research_pool=1000)
    tb = res["tradebook"]
    first_period = tb["Period Start"].min()
    bought = sorted(tb.loc[(tb["Period Start"] == first_period)
                           & tb["Action"].str.contains("BUY"), "Symbol"])
    base = _run()
    tb0 = base["tradebook"]
    bought0 = sorted(tb0.loc[(tb0["Period Start"] == first_period)
                             & tb0["Action"].str.contains("BUY"), "Symbol"])
    assert bought != bought0
    assert np.mean([int(s[1:]) for s in bought]) > np.mean([int(s[1:]) for s in bought0])


@pytest.mark.parametrize("kw", [
    dict(research_label="x", research_drop=0.2),                      # no values
    dict(research_label="x", research_pool=5),                        # no values
    dict(_research_gate=pd.Series(dtype=bool)),                       # no label
    dict(research_label="x", _research_gate=pd.Series(dtype=bool), research_gate_on="sell"),
])
def test_a_half_specified_research_filter_is_refused(kw):
    with pytest.raises(ValueError):
        _run(**kw)
