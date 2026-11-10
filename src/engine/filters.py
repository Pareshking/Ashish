"""Research filters on top of the live score: buy gates, keep gates, tie-breaks.

Owner, 10 Nov 2026: "We need other additional filters like FIP (frog in the
pan), and others ... from books related to momentum and momentum-related
research papers ... aligning with my framework." The literature behind each
function, its sample and its weaknesses are in docs/RESEARCH_FILTERS.md; the
test of each against the live book is scripts/research_filters.py.

None of this changes the score. The System-1 Sharpe composite
(calendar_momentum.py) still ranks every name. A filter here either removes a
name from the qualified list at a signal (a gate), or reorders the best few
qualified names (a tie-break), or says the market as a whole is risk-off. The
live record and every page run with all of them off (run_backtest's defaults).

Conventions, so a caller cannot mix them up:

* Every stock-level function takes a wide frame of ADJUSTED closes
  (sessions x symbols; NaN where a symbol has no print) and returns a frame
  of the same shape. The value on row t uses closes up to and including t
  only: a signal on t can read row t with no look-ahead.
* Market-level functions take one adjusted close series (the benchmark,
  SPTM total return) and return a boolean series, True = risk ON.
* Windows are in SESSIONS (252 a year, 21 a month) unless the name says
  months. A window not yet full gives NaN, never a value from fewer days.
* Where the literature says "lower is better" (FIP, MAX, volatility) the
  function returns the quantity as published; `better_high` turns any of
  them into "higher is better" for run_backtest's ``_research_values``.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

SESSIONS_PER_YEAR = 252
SESSIONS_PER_MONTH = 21


# ── helpers ──────────────────────────────────────────────────────────────────

def daily_returns(close: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Simple daily returns between consecutive prints; NaN across a missing print."""
    return close / close.shift(1) - 1.0


def better_high(values: pd.DataFrame, lower_is_better: bool) -> pd.DataFrame:
    """The same ordering with "higher is better", as run_backtest expects."""
    return -values if lower_is_better else values


def _month_end_rows(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The last session of each calendar month present in ``index``."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby(index.to_period("M")).max().to_numpy())


# ── stock level ──────────────────────────────────────────────────────────────

def frog_in_the_pan(close: pd.DataFrame, window: int = 252, skip: int = 21) -> pd.DataFrame:
    """Information discreteness, ID (Da, Gurun & Warachka 2014, eq. 1).

        ID = sgn(PRET) x (%neg - %pos)

    PRET is the cumulative return over the formation window; %neg and %pos
    are the shares of DAILY returns in that window below and above zero
    (zero-return days count in the denominator: %pos + %neg + %zero = 1).
    The paper's formation window is the past twelve months skipping the most
    recent one (``window=252, skip=21``); ``skip=0`` ends it at t.

    LOWER is better: about -1 is a winner that rose almost every day
    ("continuous information", the frog in the pan), near +1 one whose rise
    came on a few days while most days fell ("discrete"). Gray & Vogel's
    Quantitative Momentum (2016) keeps the better half by this measure among
    the top momentum decile. The value is NaN until the window is full, and
    0 where PRET is exactly 0.
    """
    window, skip = int(window), int(skip)
    if window < 2 or skip < 0:
        raise ValueError("window must be at least 2 sessions and skip at least 0")
    r = daily_returns(close)
    seen = r.notna()
    n = seen.astype(float).rolling(window, min_periods=1).sum()
    share_pos = (r > 0).astype(float).rolling(window, min_periods=1).sum() / n
    share_neg = (r < 0).astype(float).rolling(window, min_periods=1).sum() / n
    c = close.ffill()
    pret = c / c.shift(window) - 1.0
    # At least 90% of the window's sessions printed: a few holes, not a short history.
    discreteness = (np.sign(pret) * (share_neg - share_pos)).where(n >= 0.9 * window)
    return discreteness.shift(skip) if skip else discreteness


def max_daily_return(close: pd.DataFrame, window: int = 21, top: int = 1) -> pd.DataFrame:
    """MAX (Bali, Cakici & Whitelaw 2011): the largest daily return in the
    past ``window`` sessions (the paper: the previous calendar month); with
    ``top`` > 1 the mean of the ``top`` largest (their robustness MAX(5)).
    LOWER is better: high-MAX ("lottery") stocks earned less afterwards."""
    r = daily_returns(close)
    if int(top) <= 1:
        return r.rolling(int(window), min_periods=int(window) // 2 + 1).max()
    arr = r.to_numpy()
    out = np.full(arr.shape, np.nan)
    w, k = int(window), int(top)
    for t in range(w - 1, len(arr)):
        block = arr[t - w + 1: t + 1]
        ok = np.isfinite(block).sum(axis=0) >= w // 2 + 1
        srt = np.sort(np.where(np.isfinite(block), block, -np.inf), axis=0)[-k:]
        srt[~np.isfinite(srt)] = np.nan
        out[t] = np.where(ok, np.nanmean(srt, axis=0), np.nan)
    return pd.DataFrame(out, index=r.index, columns=r.columns)


def largest_move(close: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    """The largest absolute close-to-close move in the past ``window`` sessions.

    Clenow (Stocks on the Move, 2015) disqualifies a stock with a gap of more
    than 15% in the last 90 days. A gap proper is open against the previous
    close; the engine carries closes only, so this is the close-to-close move,
    which contains every gap that was not retraced the same day."""
    return daily_returns(close).abs().rolling(int(window), min_periods=int(window) // 2 + 1).max()


def trend_r2(close: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    """R-squared of a straight line through log price against time, over the
    past ``window`` sessions (Clenow's trend quality). Used here as a GATE
    only; the live score does not use R-squared and this does not change it.
    Requires every session in the window (NaN otherwise)."""
    w = int(window)
    y = np.log(close.where(close > 0))
    t = pd.Series(np.arange(len(y), dtype=float), index=y.index)
    tt = pd.DataFrame(np.repeat(t.to_numpy()[:, None], y.shape[1], axis=1),
                      index=y.index, columns=y.columns).where(y.notna())
    corr = y.rolling(w, min_periods=w).corr(tt)
    return corr ** 2


def realised_volatility(close: pd.DataFrame, window: int = 126) -> pd.DataFrame:
    """Annualised standard deviation of daily returns over ``window`` sessions.
    LOWER is safer. Not a weighting: the book stays equal weight."""
    r = daily_returns(close)
    return r.rolling(int(window), min_periods=int(window) * 3 // 4).std() * np.sqrt(SESSIONS_PER_YEAR)


def period_return(close: pd.DataFrame, window: int = 21, skip: int = 0) -> pd.DataFrame:
    """Return from ``window + skip`` sessions ago to ``skip`` sessions ago.

    ``window=21`` is last month's return (short-term reversal, Jegadeesh 1990;
    Jegadeesh & Titman 1993 skip a week or a month for it); ``window=252`` is
    the stock's own twelve-month return (absolute momentum)."""
    c = close.ffill()
    out = c.shift(int(skip)) / c.shift(int(skip) + int(window)) - 1.0
    return out.where(close.notna())


def residual_score(close: pd.DataFrame, market: pd.Series, beta_window: int = 756,
                   formation: int = 252, skip: int = 21) -> pd.DataFrame:
    """Residual (idiosyncratic) momentum, after Blitz, Huij & Martens (2011).

    The paper regresses each stock's monthly returns on the three Fama-French
    factors over 36 months and ranks on the residuals of months t-12 to t-2,
    each divided by their standard deviation. Here, with the data the engine
    has: one factor (the benchmark), daily returns, beta from a rolling
    ``beta_window`` sessions (756 = 36 months) ending at t, and the score

        mean(e) / std(e)  over the formation window ending ``skip`` sessions ago,

    e = r - beta x r_market (no intercept, so a stock's own alpha stays in e).
    HIGHER is better. A gate or tie-break only: the residual RANKING system
    the original terminal had was removed and is not brought back."""
    r = daily_returns(close)
    m = daily_returns(market.reindex(close.index).ffill())
    m_frame = pd.DataFrame(np.repeat(m.to_numpy()[:, None], r.shape[1], axis=1),
                           index=r.index, columns=r.columns).where(r.notna())
    bw = int(beta_window)
    cov = r.rolling(bw, min_periods=bw // 3).cov(m_frame)
    var = m_frame.rolling(bw, min_periods=bw // 3).var()
    beta = cov / var
    e = r - beta * m_frame
    f = int(formation)
    mu = e.rolling(f, min_periods=f * 3 // 4).mean()
    sd = e.rolling(f, min_periods=f * 3 // 4).std()
    score = mu / sd.replace(0.0, np.nan)
    return score.shift(int(skip)) if skip else score


def same_month_seasonality(close: pd.DataFrame, years: int = 10, min_years: int = 5) -> pd.DataFrame:
    """Heston & Sadka (2008): a stock's average return in the coming calendar
    month over the past ``years`` years (lags 12, 24, ... months).

    Evaluated at the last session of each month for the month that follows
    (the signal at end-January reads past Februaries); other rows are NaN.
    HIGHER is better. Needs ``min_years`` observed same months."""
    me = _month_end_rows(pd.DatetimeIndex(close.index))
    monthly = close.ffill().loc[me]
    mret = monthly / monthly.shift(1) - 1.0
    # Row t (end of month m) reads month m+1 of earlier years: shift 12k - 1.
    total = sum(mret.shift(12 * k - 1).fillna(0.0) for k in range(1, int(years) + 1))
    count = sum(mret.shift(12 * k - 1).notna().astype(int) for k in range(1, int(years) + 1))
    mean = (total / count.replace(0, np.nan)).where(count >= int(min_years))
    return mean.reindex(close.index)


def industry_momentum(close: pd.DataFrame, sector_map: Mapping[str, str], window: int = 252,
                      members: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each stock's sector's equal-weight ``window`` return (Moskowitz &
    Grinblatt 1999), broadcast to the stock; and, in ``.attrs['rank']``, the
    sector's percentile among sectors on that day (1 = the strongest).

    ``members`` (optional, bool frame like ``close``) restricts the sector
    average to the names in the index on that day."""
    ret = period_return(close, window=int(window))
    if members is not None:
        ret = ret.where(members.reindex_like(ret).fillna(False).astype(bool))
    groups = pd.Series({c: sector_map.get(c, "Other") for c in close.columns})
    by_sector = ret.T.groupby(groups).mean().T            # sessions x sectors
    rank = by_sector.rank(axis=1, pct=True)
    out = by_sector.reindex(columns=groups.to_numpy())
    out.columns = close.columns
    r_out = rank.reindex(columns=groups.to_numpy())
    r_out.columns = close.columns
    out.attrs["rank"] = r_out
    return out


def fifty_two_week_ratio(close: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """Close over its highest close of the past ``window`` sessions (George &
    Hwang 2004 use the high price; the engine's live gate uses closes too).
    HIGHER is better; the live gate requires at least 0.80."""
    hi = close.rolling(int(window), min_periods=1).max()
    return close / hi


# ── market level (True = risk on) ────────────────────────────────────────────

def _monthly(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    return s.groupby(s.index.to_period("M")).last()


def _to_sessions(monthly_flag: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """A month's flag on every session from that month's last session to the
    next month's last session (it is known at the month-end close)."""
    ends = _month_end_rows(index)
    by_period = pd.Series(ends, index=ends.to_period("M"))
    flag = monthly_flag.reindex(by_period.index)
    s = pd.Series(flag.to_numpy(), index=by_period.to_numpy()).reindex(index).ffill()
    return s


def faber_trend(market: pd.Series, months: int = 10, index: pd.DatetimeIndex | None = None) -> pd.Series:
    """Faber (2007): risk on when the month-end close is at or above the mean
    of the last ``months`` month-end closes (the 10-month SMA). Evaluated at
    each month end; carried to the sessions after it."""
    m = _monthly(market)
    on = (m >= m.rolling(int(months), min_periods=int(months)).mean()).where(
        m.rolling(int(months), min_periods=int(months)).count() >= int(months))
    idx = pd.DatetimeIndex(index if index is not None else market.dropna().index)
    return _to_sessions(on, idx).fillna(True).astype(bool)


def sma_trend(market: pd.Series, window: int = 200) -> pd.Series:
    """Clenow's index filter: risk on when the close is above its
    ``window``-session simple average (no new buys otherwise)."""
    s = pd.to_numeric(market, errors="coerce").dropna().sort_index()
    sma = s.rolling(int(window), min_periods=int(window)).mean()
    return (s > sma).where(sma.notna()).fillna(True).astype(bool)


def absolute_trend(market: pd.Series, window: int = 252, hurdle: float = 0.0) -> pd.Series:
    """Time-series momentum on the market (Moskowitz, Ooi & Pedersen 2012;
    Antonacci's absolute momentum): risk on when its ``window`` return beats
    ``hurdle`` (a T-bill return over the same window; 0 here when none is
    supplied, so this is the sign of the total return, not of the excess)."""
    s = pd.to_numeric(market, errors="coerce").dropna().sort_index()
    ret = s / s.shift(int(window)) - 1.0
    return (ret > hurdle).where(ret.notna()).fillna(True).astype(bool)


def not_bear_market(market: pd.Series, window: int = 504) -> pd.Series:
    """Daniel & Moskowitz (2016)'s bear-market indicator, inverted: risk on
    unless the market's cumulative return over the past 24 months (504
    sessions) is negative. Cooper, Gutierrez & Hameed (2004) use 36 months
    (``window=756``) for their UP/DOWN market states."""
    return absolute_trend(market, window=window, hurdle=0.0)


# ── strategy level ───────────────────────────────────────────────────────────

def volatility_target_exposure(strategy_daily: pd.Series, *, window: int = 126,
                               target: float | None = None, cap: float = 1.0,
                               rebalance: str = "M") -> pd.Series:
    """Barroso & Santa-Clara (2015)'s scaling, long only and without leverage.

    At each month end the exposure for the next month is
    min(cap, target / sigma), sigma the annualised volatility of the BOOK's
    own daily returns over the past ``window`` sessions (126, their six
    months). ``target`` None uses the median of sigma over all earlier month
    ends (an expanding median, so a quiet market keeps the full book and only
    an unusually volatile one is cut). The rest sits in cash at 0%. Returns
    the exposure on each session, known at the previous month end.
    """
    r = pd.to_numeric(strategy_daily, errors="coerce").dropna().sort_index()
    sigma = r.rolling(int(window), min_periods=int(window)).std() * np.sqrt(SESSIONS_PER_YEAR)
    ends = _month_end_rows(pd.DatetimeIndex(r.index))
    sig_m = sigma.loc[ends]
    tgt = (pd.Series(float(target), index=ends) if target is not None
           else sig_m.expanding(min_periods=6).median().shift(1))
    exp_m = (tgt / sig_m).clip(upper=float(cap)).where(sig_m.notna() & tgt.notna())
    exp_m = exp_m.fillna(1.0)
    # Known at the month-end close, applied from the next session.
    return exp_m.reindex(r.index).ffill().shift(1).fillna(1.0)


def apply_exposure(strategy_daily: pd.Series, exposure: pd.Series, cost_bps: float = 10.0) -> pd.Series:
    """Daily returns of the book scaled by ``exposure`` (rest in cash at 0%),
    charging ``cost_bps`` round trip on each change in exposure, one way, as
    the backtester charges a rebalance (half the absolute change)."""
    r = pd.to_numeric(strategy_daily, errors="coerce").fillna(0.0)
    e = exposure.reindex(r.index).ffill().fillna(1.0)
    change = e.diff().abs().fillna(0.0) / 2.0
    return e * r - change * (float(cost_bps) / 10000.0)
