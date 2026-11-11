"""The pre-registered study's engine hooks are off by default and change nothing then.

docs/MOMENTUM_PREREG.md (10 Nov 2026), scripts/research_prereg.py. Two
keywords were added to run_backtest: ``signal_offset`` (the four-offset
ensemble of section 3.1) and ``_research_score`` (S1's residual blend, S6's
horizon). With the defaults the engine must give, to the bit, what it gave
before them: the golden digest of tests/test_research_filters_plumbing.py.
"""

import numpy as np
import pandas as pd
import pytest

from tests.test_research_filters_plumbing import GOLDEN, _digest, _prices, _run, _same


def test_the_defaults_still_reproduce_the_golden_run():
    assert _digest(_run()) == GOLDEN


def test_offset_zero_and_an_identity_score_change_nothing_to_the_bit():
    base = _run()
    _same(base, _run(signal_offset=0))
    _same(base, _run(research_label="identity", _research_score=lambda on, score, members: score))


def test_an_offset_moves_every_signal_that_many_sessions_before_the_month_end():
    p = _prices()
    month_last = pd.Series(np.arange(len(p)), index=p.index).groupby(p.index.to_period("M")).last()
    res = _run(signal_offset=5)
    fills = pd.to_datetime(res["monthly"]["Period Start"])
    expected = {p.index[i + 1] for i in (month_last - 5)}
    assert len(fills) > 5
    assert set(fills) <= expected
    base_fills = set(pd.to_datetime(_run()["monthly"]["Period Start"]))
    assert not set(fills) & base_fills


def test_a_research_score_drives_the_ranking():
    p = _prices()
    seen = []

    def prefer_last(on, score, members):
        seen.append(on)
        return pd.Series(np.arange(len(score), dtype=float), index=score.index).where(score.notna())

    res = _run(research_label="last", _research_score=prefer_last)
    base = _run()
    assert seen and all(d in p.index for d in seen)
    tb, tb0 = res["tradebook"], base["tradebook"]
    first = tb["Period Start"].min()
    bought = tb.loc[(tb["Period Start"] == first) & tb["Action"].str.contains("BUY"), "Symbol"]
    bought0 = tb0.loc[(tb0["Period Start"] == first) & tb0["Action"].str.contains("BUY"), "Symbol"]
    assert np.mean([int(s[1:]) for s in bought]) > np.mean([int(s[1:]) for s in bought0])


@pytest.mark.parametrize("kw", [
    dict(_research_score=lambda on, s, m: s),                 # no label
    dict(signal_offset=-1),
])
def test_a_half_specified_hook_is_refused(kw):
    with pytest.raises(ValueError):
        _run(**kw)


def test_traded_value_weights_with_equal_sizes_are_equal_weight():
    p = _prices()
    flat = pd.DataFrame(1.0e6, index=p.index, columns=p.columns)
    base = _run()
    tv = _run(research_label="tv-flat", weight_method="Traded Value", _research_size=flat)
    assert np.allclose(tv["equity_curve"].to_numpy(), base["equity_curve"].to_numpy(), rtol=0, atol=1e-12)


def test_traded_value_weights_follow_size_under_the_stock_cap():
    p = _prices()
    size = pd.DataFrame(1.0, index=p.index, columns=p.columns)
    size.iloc[:, ::2] = 4.0                                  # even names four times the size
    size.iloc[:, 1] = np.nan                                 # no traded value: the median
    res = _RUN_TV(size)
    tb = res["tradebook"]
    first = tb[(tb["Period Start"] == tb["Period Start"].min()) & ~tb["Action"].str.contains("SELL")]
    w = first.set_index("Symbol")["Weight %"]
    big = [s for s in w.index if int(s[1:]) % 2 == 0]
    small = [s for s in w.index if int(s[1:]) % 2 == 1 and s != "S01"]
    assert big and small
    assert w[big].min() > 2.0 * w[small].max()
    assert w.max() <= 15.0 + 1e-9
    assert abs(w.sum() - 100.0) < 1e-6


def _RUN_TV(size):  # noqa: N802 - local helper
    p = _prices()
    sec = {c: c for c in p.columns}                          # no sector cap binds
    from tests.test_research_filters_plumbing import _RUN as raw
    return raw("tv", p, top_n=10, buffer_n=20, cost_bps=10.0, sector_map=sec, stock_cap=0.15,
               _benchmark_close=p.mean(axis=1), backtest_months=14, stateful_history=True,
               weight_method="Traded Value", _research_size=size, research_label="tv")


def test_traded_value_needs_its_frame_and_a_label():
    p = _prices()
    with pytest.raises(ValueError):
        _run(weight_method="Traded Value")
    with pytest.raises(ValueError):
        _run(_research_size=pd.DataFrame(1.0, index=p.index, columns=p.columns))
