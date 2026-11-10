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
