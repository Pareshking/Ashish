"""The research filters (src/engine/filters.py) on synthetic prices.

Each definition is checked against a hand computation and its sign against
the source: FIP / information discreteness as Da, Gurun & Warachka (2014)
eq. 1 (lower = continuous = better), MAX as Bali, Cakici & Whitelaw (2011),
and so on. None reads a later row than the one it is reported on.
"""

import numpy as np
import pandas as pd
import pytest

from src.engine import filters as f


def _frame(cols: dict, start="2020-01-01") -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    return pd.DataFrame(cols, index=pd.bdate_range(start, periods=n), dtype=float)


def _from_returns(rets: np.ndarray, p0=100.0) -> np.ndarray:
    return p0 * np.concatenate([[1.0], np.cumprod(1 + np.asarray(rets, float))])


# ── frog in the pan ──────────────────────────────────────────────────────────

def test_fip_matches_the_paper_formula_on_a_hand_count():
    # 10 daily returns: 7 up, 2 down, 1 flat; cumulative positive.
    rets = [0.01, 0.01, -0.005, 0.01, 0.0, 0.01, 0.01, -0.005, 0.01, 0.01]
    px = _frame({"A": _from_returns(rets)})
    out = f.frog_in_the_pan(px, window=10, skip=0)
    # sgn(PRET) = +1, %neg = 2/10, %pos = 7/10 -> ID = -0.5
    assert out["A"].iloc[-1] == pytest.approx(-0.5)
    assert out["A"].iloc[:-1].isna().all()          # window not full before


def test_fip_continuous_winner_scores_below_a_discrete_winner_with_the_same_return():
    n = 252
    smooth = np.full(n, (1.5 ** (1 / n)) - 1)          # +50%, up every day
    jumpy = np.full(n, -0.001)
    jumpy[::21] = 0.0                                   # some flat days
    # Two big days lift the jumpy stock to the same +50%.
    jumpy[100] = jumpy[200] = 0.0
    need = 1.5 / np.prod(1 + jumpy)
    jumpy[100] = jumpy[200] = np.sqrt(need) - 1
    px = _frame({"S": _from_returns(smooth), "J": _from_returns(jumpy)})
    out = f.frog_in_the_pan(px, window=n, skip=0).iloc[-1]
    assert px["S"].iloc[-1] / px["S"].iloc[0] == pytest.approx(px["J"].iloc[-1] / px["J"].iloc[0])
    assert out["S"] == pytest.approx(-1.0)
    assert out["J"] > 0.8                              # mostly down days: discrete
    assert out["S"] < out["J"]


def test_fip_flips_sign_for_a_loser_and_skip_shifts_the_window():
    rets = [-0.01] * 8 + [0.01] * 2                    # a loser: down 8 of 10
    px = _frame({"L": _from_returns(rets + [0.0] * 3)})
    out = f.frog_in_the_pan(px, window=10, skip=0)
    # sgn(PRET) = -1, %neg - %pos = 0.6 -> ID = -0.6 (a continuous loser)
    assert out["L"].iloc[10] == pytest.approx(-0.6)
    skipped = f.frog_in_the_pan(px, window=10, skip=3)
    assert skipped["L"].iloc[13] == pytest.approx(out["L"].iloc[10])


def test_fip_uses_no_later_price():
    rng = np.random.default_rng(1)
    px = _frame({"A": _from_returns(rng.normal(0.001, 0.01, 300))})
    full = f.frog_in_the_pan(px, window=60, skip=5)
    cut = f.frog_in_the_pan(px.iloc[:200], window=60, skip=5)
    pd.testing.assert_series_equal(full["A"].iloc[:200], cut["A"])


# ── the others ───────────────────────────────────────────────────────────────

def test_max_daily_return_and_its_top_k_mean():
    rets = [0.01, 0.05, -0.02, 0.03, 0.0]
    px = _frame({"A": _from_returns(rets)})
    assert f.max_daily_return(px, window=5)["A"].iloc[-1] == pytest.approx(0.05)
    assert f.max_daily_return(px, window=5, top=2)["A"].iloc[-1] == pytest.approx(0.04)


def test_largest_move_sees_a_fall_as_well_as_a_rise():
    px = _frame({"A": _from_returns([0.01, -0.2, 0.01, 0.01])})
    assert f.largest_move(px, window=4)["A"].iloc[-1] == pytest.approx(0.2)


def test_trend_r2_is_one_on_a_straight_log_line_and_low_on_noise():
    rng = np.random.default_rng(2)
    px = _frame({"line": 100 * np.exp(0.002 * np.arange(120)),
                 "noise": 100 * np.exp(rng.normal(0, 0.02, 120))})
    r2 = f.trend_r2(px, window=90).iloc[-1]
    assert r2["line"] == pytest.approx(1.0)
    assert r2["noise"] < 0.5
    assert f.trend_r2(px, window=90)["line"].iloc[:89].isna().all()


def test_realised_volatility_is_annualised():
    rets = np.tile([0.01, -0.01], 100)
    px = _frame({"A": _from_returns(rets)})
    v = f.realised_volatility(px, window=126)["A"].iloc[-1]
    assert v == pytest.approx(np.std(rets[-126:], ddof=1) * np.sqrt(252), rel=1e-3)


def test_period_return_with_skip():
    px = _frame({"A": [100, 110, 121, 133.1, 146.41]})
    assert f.period_return(px, window=2)["A"].iloc[-1] == pytest.approx(0.21)
    assert f.period_return(px, window=2, skip=1)["A"].iloc[-1] == pytest.approx(0.21)
    assert np.isnan(f.period_return(px, window=4, skip=1)["A"].iloc[-1])


def test_residual_score_removes_the_market_and_keeps_the_stock_own_drift():
    rng = np.random.default_rng(4)
    n = 900
    m = rng.normal(0.0005, 0.01, n)
    eps = rng.normal(0, 0.01, (n, 2))
    beta_only = 1.5 * m + eps[:, 0]                    # market and noise only
    alpha = 1.5 * m + eps[:, 1] + 0.002                # plus its own drift
    px = _frame({"B": _from_returns(beta_only), "A": _from_returns(alpha)})
    mkt = pd.Series(_from_returns(m), index=px.index)
    s = f.residual_score(px, mkt, beta_window=756, formation=252, skip=21).iloc[-1]
    assert s["A"] > s["B"]
    assert abs(s["B"]) < 0.08
    assert s["A"] > 0.1


def test_same_month_seasonality_reads_next_month_of_earlier_years():
    idx = pd.bdate_range("2010-01-01", "2016-12-31")
    # Every February the stock rises 10%, otherwise it is flat.
    daily = pd.Series(0.0, index=idx)
    for y in range(2010, 2017):
        feb = idx[(idx.year == y) & (idx.month == 2)]
        daily.loc[feb] = 1.1 ** (1 / len(feb)) - 1
    px = pd.DataFrame({"A": 100 * (1 + daily).cumprod(), "B": 100.0}, index=idx)
    s = f.same_month_seasonality(px, years=10, min_years=5)
    end_jan_2016 = idx[(idx.year == 2016) & (idx.month == 1)][-1]
    end_feb_2016 = idx[(idx.year == 2016) & (idx.month == 2)][-1]
    assert s.loc[end_jan_2016, "A"] == pytest.approx(0.10, rel=1e-6)   # next month is February
    assert s.loc[end_feb_2016, "A"] == pytest.approx(0.0, abs=1e-12)    # next is March
    assert s.loc[end_jan_2016, "B"] == pytest.approx(0.0)
    assert s.loc[idx[5]].isna().all()                                    # not a month end


def test_industry_momentum_is_the_sector_average():
    px = _frame({"A": [100, 110], "B": [100, 130], "C": [100, 90]})
    out = f.industry_momentum(px, {"A": "X", "B": "X", "C": "Y"}, window=1)
    assert out.iloc[-1].tolist() == pytest.approx([0.2, 0.2, -0.1])
    assert out.attrs["rank"].iloc[-1].tolist() == pytest.approx([1.0, 1.0, 0.5])


def test_fifty_two_week_ratio():
    px = _frame({"A": [100, 120, 90, 108]})
    assert f.fifty_two_week_ratio(px)["A"].tolist() == pytest.approx([1.0, 1.0, 0.75, 0.9])


# ── market gates ─────────────────────────────────────────────────────────────

def _market(path):
    idx = pd.bdate_range("2019-01-01", periods=len(path))
    return pd.Series(path, index=idx, dtype=float)


def test_faber_trend_is_decided_at_month_end_and_held_through_the_next_month():
    up = np.linspace(100, 200, 300)
    down = np.linspace(200, 120, 120)
    m = _market(np.concatenate([up, down]))
    on = f.faber_trend(m, months=10)
    assert on.iloc[260]                               # rising: on
    assert not on.iloc[-1]                            # three months of falls: off
    # Decided at the month-end close: constant from the month's first session
    # to the one before its last.
    month = on.index.to_period("M")
    for _, g in on.groupby(month):
        assert g.iloc[:-1].nunique() <= 1


def test_sma_and_absolute_and_bear_gates():
    m = _market(np.concatenate([np.linspace(100, 150, 600), np.linspace(150, 90, 300)]))
    assert f.sma_trend(m, 200).iloc[500] and not f.sma_trend(m, 200).iloc[-1]
    assert f.absolute_trend(m, 252).iloc[500] and not f.absolute_trend(m, 252).iloc[-1]
    assert f.not_bear_market(m, 504).iloc[550] and not f.not_bear_market(m, 504).iloc[-1]
    assert f.sma_trend(m, 200).iloc[:199].all()       # unknown: risk on, no gate


# ── volatility targeting ─────────────────────────────────────────────────────

def test_volatility_target_cuts_exposure_after_a_stormy_spell_and_never_levers():
    rng = np.random.default_rng(5)
    idx = pd.bdate_range("2020-01-01", periods=800)
    vol = np.where(np.arange(800) < 500, 0.01, 0.03)
    r = pd.Series(rng.normal(0, vol), index=idx)
    e = f.volatility_target_exposure(r, window=126)
    assert e.max() <= 1.0
    assert e.iloc[:400].min() > 0.6
    assert e.iloc[-50:].mean() < 0.6
    # Known at the previous month end: a change appears only on a month's first session.
    changes = e.index[e.diff().fillna(0) != 0]
    first_sessions = set(pd.Series(idx, index=idx).groupby(idx.to_period("M")).min())
    assert set(changes) <= first_sessions
    out = f.apply_exposure(r, e, cost_bps=10.0)
    assert out.iloc[0] == pytest.approx(r.iloc[0] * e.iloc[0])
