"""scripts/research_prereg.py: the overlay arithmetic and the residual score.

docs/MOMENTUM_PREREG.md S2/S3/C1 (an SPY sleeve beside the book) and S1
(three-factor residual momentum). Synthetic data only.
"""

import numpy as np
import pandas as pd

from scripts.research_prereg import overlay, residual_scores


def _book(n=90, seed=1):
    idx = pd.bdate_range("2021-01-04", periods=n)
    rng = np.random.default_rng(seed)
    book = pd.Series(rng.normal(0.0005, 0.01, n), index=idx)
    spy = pd.Series(rng.normal(0.0003, 0.008, n), index=idx)
    fills = [idx[0], idx[30], idx[60]]
    monthly = pd.DataFrame({"Period Start": fills, "Turnover %": [50.0, 20.0, 30.0]})
    return idx, book[book.index > fills[0]], spy, monthly


def test_full_weight_is_the_book_and_zero_weight_is_spy_less_its_entry_cost():
    idx, book, spy, monthly = _book()
    r, tv, w = overlay(book, monthly, spy, lambda m: 1.0, 10.0, idx)
    assert np.allclose(r.to_numpy(), book.to_numpy())
    assert np.allclose(tv.to_numpy(), [50.0, 20.0, 30.0])
    r0, tv0, _ = overlay(book, monthly, spy, lambda m: 0.0, 10.0, idx)
    exp = spy.reindex(book.index).copy()
    exp.iloc[0] -= 0.0005                          # half of 10 bps on the whole sleeve
    assert np.allclose(r0.to_numpy(), exp.to_numpy())
    assert np.allclose(tv0.to_numpy(), [50.0, 0.0, 0.0])


def test_a_weight_change_costs_its_size_once_and_the_split_resets_at_each_fill():
    idx, book, spy, monthly = _book()
    ws = iter([0.5, 0.8, 0.8])
    seq = {}

    def weight(m):
        if m not in seq:
            seq[m] = next(ws)
        return seq[m]

    r, tv, w = overlay(book, monthly, spy, weight, 10.0, idx)
    first = book.index[book.index > idx[30]][0]
    b, s = book.loc[first], spy.loc[first]
    assert np.isclose(r.loc[first], 0.8 * b + 0.2 * s - 0.3 * 0.001)
    assert np.isclose(tv.iloc[1], 0.8 * 20.0 + 30.0)


def test_residual_score_excludes_the_intercept_and_needs_36_months():
    months = pd.period_range("2008-01", "2012-12", freq="M")
    rng = np.random.default_rng(4)
    ff = pd.DataFrame(rng.normal(0, 0.03, (len(months), 3)), index=months, columns=["Mkt-RF", "SMB", "HML"])
    ff["RF"] = 0.001
    beta = np.array([1.1, 0.2, -0.3])
    noise = rng.normal(0, 0.02, len(months))
    base = ff[["Mkt-RF", "SMB", "HML"]].to_numpy() @ beta + 0.001 + noise
    mret = pd.DataFrame({"D": base, "E": base + 0.01, "F": base}, index=months)
    mret.loc[months[-20]:, "F"] = np.nan                      # a short history
    idx = pd.DatetimeIndex([m.end_time.normalize() for m in months])
    close = pd.DataFrame(100 * np.cumprod(1 + mret.fillna(0).to_numpy(), axis=0), index=idx, columns=mret.columns)
    close.loc[idx[-20]:, "F"] = np.nan
    last = residual_scores(close, ff)[months[-1]]
    # The intercept absorbs E's extra 1% a month; residuals exclude it, so E scores higher.
    assert np.isfinite(last["D"]) and last["E"] > last["D"]
    assert np.isnan(last["F"])


def test_stage2_has_48_combinations_and_a_sane_deflated_sharpe():
    from scripts.research_prereg_stage2 import combo_name, combos, deflated_sharpe, n_components

    ks = combos()
    assert len(ks) == 48 and len(set(ks)) == 48
    assert combo_name("base", "none", False) == "base"
    assert combo_name("S1+S7", "S2", True) == "S1+S7+S2+S5" and n_components("S1+S7", "S2", True) == 4
    # More trials with the same spread raise the bar; a normal series of Sharpe 1 over 9 years passes alone.
    few = deflated_sharpe(1.0, [0.9, 1.0, 1.1], 2268, 0.0, 3.0)
    many = deflated_sharpe(1.0, [0.9, 1.0, 1.1] * 16, 2268, 0.0, 3.0)
    assert many["sr0_daily"] > few["sr0_daily"] and many["dsr"] < few["dsr"]
    assert 0.0 < many["dsr"] < 1.0
