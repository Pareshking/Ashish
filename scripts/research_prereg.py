#!/usr/bin/env python3
"""The pre-registered momentum study (docs/MOMENTUM_PREREG.md, 10 Nov 2026).

    python scripts/research_prereg.py params                      # S3's frozen parameters
    python scripts/research_prereg.py checks [--extra-prices P]   # section 2 checks
    python scripts/research_prereg.py run --out DIR [--workers 3] [--extra-prices P | --no-extra]
    python scripts/research_prereg.py report --out DIR

Implements exactly the shortlist of section 7 (S1-S7, C1, C2) with section 3's
runs, statistics and verdicts. Nothing here is tuned; every choice the spec
leaves open is listed in CHOICES and printed into the report.

Runs: the base book (section 1: top 20 of the qualified, keep while in the top
40, above the 50-day EMA, within 20% of the 52-week high, 5% stock and 40% GICS
sector caps, monthly, no six-monthly reset, no hold cap) and the engine
variants S1, S4, S6, S7 and C2, each at signal offsets 0, 5, 10 and 15 sessions
before the month's last session and at 10 and 20 bps: 48 backtests on
point-in-time S&P 500 membership (src.engine.index_universe.index_history).
S2, S3 and C1 are overlays on the base and S1 runs' daily returns with an SPY
(total return) sleeve; S5 is the four base offsets held as equal tranches.
Each run's daily net returns and monthly table are saved, so a stopped run resumes.

--extra-prices: a long parquet (Date, Symbol, High, Low, Close, Volume; Close a
total-return close) of research-only prices for former members the store lacks.
Its symbols are added as extra columns in memory; the store is never written.
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.research_filters import block_indices, live_kwargs, max_drawdown  # noqa: E402

SCRATCH = Path("/tmp/claude-0/-home-user/98ffa510-1b54-5cd0-a724-31f84e65722d/scratchpad")
DEFAULT_EXTRA = SCRATCH / "research_extra_prices.parquet"
FRENCH_DIR = SCRATCH / "french"
FRENCH_FILES = {
    "ff3_m": "F-F_Research_Data_Factors", "ff3_d": "F-F_Research_Data_Factors_daily",
    "mom_m": "F-F_Momentum_Factor", "mom_d": "F-F_Momentum_Factor_daily",
}
FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"

TRADING_DAYS = 252
PRICE_START = "2008-01-01"
OFFSETS = (0, 5, 10, 15)
COSTS = (10.0, 20.0)
SEED = 20261110
N_DRAWS = 2000
BLOCK = 63
SECONDARY_START = "2020-01-01"

ENGINE = ("base", "S1", "S4", "S6", "S7", "C2")
SHORTLIST = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "C1", "C2")
KIND = {"S1": "selection", "S4": "selection", "S6": "selection", "S7": "selection", "C2": "selection",
        "S2": "overlay", "S3": "overlay", "C1": "overlay", "S5": "tranching"}
TEXT = {
    "S1": "Residual momentum (FF3, 36m, 11 residuals, standardised) blended 0.75/0.25 into the score",
    "S2": "Book scaled by min(1, 12% / UMD 126-day realised vol), remainder in SPY",
    "S3": "Daniel-Moskowitz dynamic weight (frozen 1927-2007), remainder in SPY",
    "S4": "Buy gate: not in the low-return / high-turnover cell (median splits, members)",
    "S5": "Four equal tranches, signals 0/5/10/15 sessions before month end",
    "S6": "Horizon: 9M and 12M replaced by a 12-7 window (30%)",
    "S7": "Buy gate: not in the 20% of the qualified with the lowest MA(21)/MA(200)",
    "C1": "S1 scaled by S2's weight, remainder in SPY",
    "C2": "S1 plus the 12-month sector-momentum buy gate (industry_top)",
}

# Every interpretation the spec left open, fixed before the first run.
CHOICES = [
    "Base keywords: live_kwargs() (TRACK_RECORD_CONFIG) with members_only_scoring_from, ema_warmup_from, "
    "hold_cap, hold_cap_from, buy_size and weight_reset_months set to None (all forward-dated to the 30 Nov "
    "2026 signal, so off in the sample either way). The composite is therefore z-scored over every column "
    "with a price (all ever-members loaded), as the record does before 30 Nov 2026; membership restricts "
    "who may be held.",
    "Offsets: the signal is the session 0/5/10/15 sessions before each calendar month's last session "
    "(run_backtest signal_offset). 'Month m' is the calendar month holding the signal.",
    "Common start: m0 = the first month at which S1 has 36 monthly returns ending m-1 (and the membership "
    "covers the signal). Every run starts with its own offset's signal in m0; all are evaluated on the "
    "sessions after the offset-0 fill of m0 (the latest first fill) to the last session of the last "
    "complete month.",
    "Secondary sample: the same runs, sessions from 1 Jan 2020 (state carried from 2011, not a fresh start).",
    "S1: monthly returns are calendar month-end to month-end at every offset (they must line up with "
    "French's months); RES is computed over every stock, then z-scored over the day's members; RES of a "
    "member without 36 returns is 0 after standardisation. z(base) is the winsorised z of the composite "
    "over the day's members with a score.",
    "S4 and S6 under an offset: 'the end of month k' is the session the offset shifts it to (offset o: o "
    "sessions before month k's last session), so each offset is a pure time shift. S4's month-m return is "
    "the close at the signal over the close at the previous shifted month end; its volume is summed over "
    "the sessions after that to the signal. S6's 12-7 window runs from the shifted end of m-12 to the "
    "shifted end of m-6; its opening and closing prices use the 5-session stale-anchor rule.",
    "S4: shares = market cap in data/market_caps.csv / the store's adjusted close on that file's AsOf date; "
    "a member with no market cap (most former members) has no turnover, is left out of the sort and "
    "passes. Median splits: low return = below the members' median, high turnover = above it.",
    "S7 and the S1-fallback wording: the engine keywords named by the spec are used (research_drop over all "
    "the qualified, held names exempt), not a recount over the not-held names only. A name with fewer than "
    "200 closes passes (MAD set to +inf).",
    "S2: sigma over the 126 French daily UMD sessions ending at the last session of month m-1, "
    "sqrt(252 * mean(u^2)). Downside robustness: mean over the same 126 of u^2 for u<0 only, times 2.",
    "S3: I_B from compounded monthly Mkt-RF+RF over k-23..k; sigma^2_mkt = sample variance (ddof 1) of daily "
    "Mkt-RF over the 126 sessions to the end of month k; sigma^2_UMD = 21 * mean(u^2) over the same window; "
    "regression on k = Jan 1927 .. Nov 2007 (UMD_{k+1} up to Dec 2007), kappa = 1/median(raw_k) over k in "
    "1927-2007 with all inputs.",
    "Overlays: at each fill the split is reset to w; cost = cost_bps x |w_m - w_{m-1}| on the first session "
    "after the fill, plus the book's own (full-size) costs scaled by w; the first fill pays cost_bps/2 on the "
    "SPY sleeve's (1-w_0), as the engine charges half a round trip to establish a book. Turnover: "
    "w x book turnover + |dw| (one way).",
    "S5: sub-book j is the base run at offset 5j, each worth a quarter at the common start, never rebalanced. "
    "Its own four-offset dispersion is zero by construction (it holds all four schedules), so the "
    "'dispersion falls by a third' test is met mechanically and the verdict rests on the CAGR test; "
    "dispersion = sample standard deviation (ddof 1) of the four base CAGRs. Hoffstein's RTL (tracking "
    "error of each single schedule against the tranched book) is reported beside it. S5 not passing is "
    "'reject' if its CAGR shortfall exceeds 0.5 pt in both halves, else 'inconclusive'.",
    "Statistics: CAGR = compound daily growth to the power 252/sessions; Sharpe = mean(r - RF)/sd(r - RF) * "
    "sqrt(252) with French daily RF (sessions after French's last day use its last RF); TE and IR against "
    "SPY_TR (data/benchmarks.csv); turnover a year = one-way turnover % of the fills in the sample / years. "
    "Variant-minus-base gaps are means over the four offsets; the bootstrap applies one set of block "
    "indices to every series and RF.",
    "Verdict (3.3) on each sample: pass = primary gap > 0 in both halves of that sample, ahead in >= 90% of "
    "draws, gap > 0 at all four offsets and > 0 at 20 bps, mean max-drawdown gap >= -2 pts, mean turnover "
    "gap <= +15 pts a year. Reject = behind in both halves or ahead in <= 20% of draws. Else inconclusive.",
]


# ── French data ──────────────────────────────────────────────────────────────

def _french_csv(name: str) -> Path:
    return FRENCH_DIR / "csv" / f"{name}.csv"


def fetch_french() -> dict:
    """Download (once) and cache the four French files; return their vintage."""
    import urllib.request
    import zipfile

    (FRENCH_DIR / "zips").mkdir(parents=True, exist_ok=True)
    (FRENCH_DIR / "csv").mkdir(parents=True, exist_ok=True)
    info_path = FRENCH_DIR / "vintage.json"
    info = json.loads(info_path.read_text()) if info_path.exists() else {}
    for name in FRENCH_FILES.values():
        if _french_csv(name).exists():
            continue
        z = FRENCH_DIR / "zips" / f"{name}_CSV.zip"
        if not z.exists():
            urllib.request.urlretrieve(FRENCH_URL.format(name), z)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(FRENCH_DIR / "csv")
        info[name] = {"downloaded": pd.Timestamp.now().date().isoformat()}
    for name in FRENCH_FILES.values():
        head = _french_csv(name).read_text(errors="replace").splitlines()[0]
        vint = "".join(ch for ch in head.split("CRSP")[0] if ch.isdigit())[-6:]
        info.setdefault(name, {})["vintage"] = vint
        info[name].setdefault("downloaded", pd.Timestamp(
            (FRENCH_DIR / "zips" / f"{name}_CSV.zip").stat().st_mtime, unit="s").date().isoformat())
    info_path.write_text(json.dumps(info, indent=2))
    return info


def _parse_french(name: str, daily: bool) -> pd.DataFrame:
    rows, cols, started = [], None, False
    for line in _french_csv(name).read_text(errors="replace").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if not started:
            if len(parts) > 1 and parts[0] == "" and parts[1]:
                cols, started = parts[1:], True
            continue
        key = parts[0]
        width = 8 if daily else 6
        if len(key) != width or not key.isdigit():
            if rows:
                break                    # the annual block follows the monthly one
            continue
        rows.append([key, *[float(x) for x in parts[1:1 + len(cols)]]])
    df = pd.DataFrame(rows, columns=["key", *cols])
    idx = (pd.to_datetime(df["key"], format="%Y%m%d") if daily
           else pd.PeriodIndex(pd.to_datetime(df["key"], format="%Y%m"), freq="M"))
    out = df.drop(columns="key").set_index(pd.Index(idx)) / 100.0
    out.columns = [c.strip() for c in out.columns]
    return out


def load_french() -> dict:
    vint = fetch_french()
    ff3_m = _parse_french(FRENCH_FILES["ff3_m"], False)
    ff3_d = _parse_french(FRENCH_FILES["ff3_d"], True)
    mom_m = _parse_french(FRENCH_FILES["mom_m"], False).iloc[:, 0].rename("UMD")
    mom_d = _parse_french(FRENCH_FILES["mom_d"], True).iloc[:, 0].rename("UMD")
    return {"ff3_m": ff3_m, "ff3_d": ff3_d, "umd_m": mom_m, "umd_d": mom_d, "vintage": vint}


def _daily_window_end(daily_index: pd.DatetimeIndex, month: pd.Period) -> int | None:
    """Position of the last French session in ``month`` (None if not published)."""
    pos = int(daily_index.searchsorted(month.end_time, side="right")) - 1
    if pos < 0 or daily_index[pos].to_period("M") != month:
        return None
    return pos


def s2_sigma(umd_d: pd.Series, month: pd.Period, downside: bool = False) -> float:
    pos = _daily_window_end(umd_d.index, month)
    if pos is None or pos + 1 < 126:
        return float("nan")
    u = umd_d.iloc[pos - 125: pos + 1].to_numpy()
    sq = np.where(u < 0, u * u, 0.0) * 2.0 if downside else u * u
    return float(math.sqrt(TRADING_DAYS * sq.mean()))


def s2_weight(umd_d: pd.Series, month: pd.Period, downside: bool = False) -> float:
    s = s2_sigma(umd_d, month, downside)
    return float(min(1.0, 0.12 / s)) if s > 0 else float("nan")


def dm_inputs(fr: dict) -> pd.DataFrame:
    """Per month k: I_B, sigma^2_mkt (daily), sigma^2_UMD (monthly units), UMD_{k+1}."""
    mkt_m = fr["ff3_m"]["Mkt-RF"] + fr["ff3_m"]["RF"]
    cum24 = np.exp(np.log1p(mkt_m).rolling(24, min_periods=24).sum()) - 1.0
    ib = (cum24 < 0).astype(float).where(cum24.notna())
    d_mkt = fr["ff3_d"]["Mkt-RF"]
    u = fr["umd_d"]
    out = {}
    for k in fr["ff3_m"].index:
        pm, pu = _daily_window_end(d_mkt.index, k), _daily_window_end(u.index, k)
        if pm is None or pu is None or pm < 125 or pu < 125:
            continue
        s2m = float(np.var(d_mkt.iloc[pm - 125: pm + 1].to_numpy(), ddof=1))
        s2u = float(21.0 * np.mean(u.iloc[pu - 125: pu + 1].to_numpy() ** 2))
        out[k] = {"IB": ib.get(k, np.nan), "s2m": s2m, "s2u": s2u,
                  "umd_next": fr["umd_m"].get(k + 1, np.nan)}
    return pd.DataFrame(out).T


def dm_parameters(fr: dict) -> dict:
    """S3's gamma0, gamma1, kappa on Jan 1927 - Dec 2007, frozen."""
    d = dm_inputs(fr)
    lo, hi = pd.Period("1927-01", "M"), pd.Period("2007-12", "M")
    est = d[(d.index >= lo) & (d.index <= hi - 1)].dropna()
    x = est["IB"] * est["s2m"]
    X = np.column_stack([np.ones(len(est)), x.to_numpy()])
    g, *_ = np.linalg.lstsq(X, est["umd_next"].to_numpy(), rcond=None)
    allk = d[(d.index >= lo) & (d.index <= hi)].dropna(subset=["IB", "s2m", "s2u"])
    raw = (g[0] + g[1] * allk["IB"] * allk["s2m"]) / allk["s2u"]
    kappa = 1.0 / float(np.median(raw))
    return {"gamma0": float(g[0]), "gamma1": float(g[1]), "kappa": kappa,
            "n_regression": int(len(est)), "first_k": str(est.index[0]), "last_k": str(est.index[-1]),
            "n_kappa": int(len(allk)), "share_w_below_1_1927_2007": float((kappa * raw < 1).mean())}


def s3_weight(dm: pd.DataFrame, par: dict, month: pd.Period) -> float:
    k = month - 1
    if k not in dm.index:
        return float("nan")
    row = dm.loc[k]
    raw = (par["gamma0"] + par["gamma1"] * row["IB"] * row["s2m"]) / row["s2u"]
    return float(min(1.0, max(0.0, par["kappa"] * raw)))


# ── inputs ───────────────────────────────────────────────────────────────────

def load_inputs(extra_path: str | None) -> dict:
    from src.engine import index_universe as iu
    from src.engine.model_record import record_sector_map
    from src.loaders import benchmark_store
    from src.loaders import price_store as ps

    hist = iu.index_history("sp500")
    if not hist:
        raise SystemExit("No point-in-time S&P 500 timeline (index_history('sp500')).")
    ever = sorted(iu.ever_members(hist))
    w = ps.read_wide(["Close", "Volume"], start=PRICE_START, symbols=ever)
    close = ps.adjusted_close(w["Close"], ps.read_actions())
    volume = w["Volume"]
    store_cols = set(close.columns)
    extra_added: list[str] = []
    if extra_path:
        ex = pd.read_parquet(extra_path)
        ex["Date"] = pd.to_datetime(ex["Date"])
        ex = ex[ex["Date"] >= pd.Timestamp(PRICE_START)]
        ec = ex.pivot_table(index="Date", columns="Symbol", values="Close", aggfunc="last")
        ev = ex.pivot_table(index="Date", columns="Symbol", values="Volume", aggfunc="last")
        extra_added = sorted(c for c in ec.columns if c not in store_cols)
        idx = close.index
        close = pd.concat([close, ec[extra_added].reindex(idx)], axis=1)
        volume = pd.concat([volume, ev.reindex(columns=extra_added).reindex(idx)], axis=1)
    close = close.dropna(axis=1, how="all")
    volume = volume.reindex(columns=close.columns)
    spy = pd.to_numeric(benchmark_store.history("max", "SPY_TR"), errors="coerce").dropna()
    as_of = min(close.index[-1], spy.index[-1])
    close, volume, spy = close.loc[:as_of], volume.loc[:as_of], spy.loc[:as_of]
    end_month = pd.Period(as_of, freq="M") - 1        # the last complete month
    end_date = close.index[close.index <= end_month.end_time][-1]
    sector_map = record_sector_map(close.columns)
    return {"close": close, "volume": volume, "spy": spy, "membership": hist,
            "sector_map": sector_map, "end_month": end_month, "end_date": end_date,
            "ever": ever, "store_cols": store_cols, "extra_added": extra_added,
            "extra_path": extra_path}


def month_last_rows(index: pd.DatetimeIndex) -> pd.Series:
    """Period -> position of the month's last session."""
    return pd.Series(np.arange(len(index)), index=index).groupby(index.to_period("M")).last()


def signal_rows(index: pd.DatetimeIndex, offset: int) -> pd.Series:
    return month_last_rows(index) - int(offset)


def first_month(inp: dict) -> pd.Period:
    """m0: the first month S1 can be computed (36 monthly returns to m-1) and
    the membership covers the signal at every offset."""
    from src.engine.membership import members_on

    idx = inp["close"].index
    first_ret = pd.Period(idx[0], freq="M") + 1
    m0 = first_ret + 36
    while True:
        rows = signal_rows(idx, max(OFFSETS))
        sig = idx[int(rows[m0])]
        if members_on(inp["membership"], sig.date()) is not None:
            return m0
        m0 += 1


def schedule(inp: dict) -> dict:
    idx = inp["close"].index
    m0 = first_month(inp)
    starts = {}
    for o in OFFSETS:
        s = int(signal_rows(idx, o)[m0])
        starts[o] = idx[s + 1]
    d0 = starts[0]                                   # the latest first fill
    return {"m0": m0, "history_start": starts, "d0": d0}


def coverage(inp: dict, m0: pd.Period, cols: set[str]) -> dict:
    """Point-in-time member-months (month-end signals m0 .. end) with a price."""
    from src.engine.membership import members_on

    close = inp["close"]
    rows = month_last_rows(close.index)
    have = close.notna()
    total = priced = 0
    missing_syms: dict[str, int] = {}
    by_year: dict[int, list[int]] = {}
    for m, r in rows.items():
        if m < m0 or m > inp["end_month"]:
            continue
        d = close.index[int(r)]
        mem = members_on(inp["membership"], d.date(), canonical=True) or set()
        win = have.iloc[max(0, int(r) - 5): int(r) + 1]
        for s in mem:
            total += 1
            ok = s in cols and s in win.columns and bool(win[s].any())
            priced += ok
            by_year.setdefault(d.year, [0, 0])
            by_year[d.year][0] += 1
            by_year[d.year][1] += ok
            if not ok:
                missing_syms[s] = missing_syms.get(s, 0) + 1
    return {"member_months": total, "with_price": priced, "share": priced / total if total else float("nan"),
            "symbols_missing": len(missing_syms),
            "missing_top": sorted(missing_syms.items(), key=lambda x: -x[1])[:40],
            "by_year": {y: round(v[1] / v[0], 4) for y, v in sorted(by_year.items())}}


# ── variant inputs ───────────────────────────────────────────────────────────

def residual_scores(close: pd.DataFrame, ff3_m: pd.DataFrame) -> dict[pd.Period, pd.Series]:
    """S1's RES_i for every signal month m (French data through m-1)."""
    rows = month_last_rows(close.index)
    mclose = close.ffill(limit=5).iloc[rows.to_numpy()]
    mclose.index = rows.index
    mret = mclose / mclose.shift(1) - 1.0
    out = {}
    fac = ff3_m.reindex(mret.index)
    for m in mret.index[37:]:
        win = pd.period_range(m - 36, m - 1, freq="M")
        f = fac.loc[win]
        if f.isna().any().any():
            continue
        y = mret.loc[win].sub(f["RF"].to_numpy(), axis=0)
        ok = y.notna().all(axis=0)
        res = pd.Series(np.nan, index=close.columns)
        if ok.sum() >= 3:
            Y = y.loc[:, ok].to_numpy()
            F = f[["Mkt-RF", "SMB", "HML"]].to_numpy()
            X = np.column_stack([np.ones(36), F])
            beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
            e = Y[-11:] - F[-11:] @ beta[1:]                    # intercept excluded, m-11 .. m-1
            dev = e - e.mean(axis=0)
            den = np.sqrt((dev * dev).sum(axis=0))
            res[ok[ok].index] = np.where(den > 0, e.sum(axis=0) / np.where(den > 0, den, 1), np.nan)
        out[m] = res
    return out


def s1_score_fn(res: dict[pd.Period, pd.Series]):
    from src.engine.calendar_momentum import winsorised_z

    def fn(on, score, members):
        if members is None:
            raise RuntimeError(f"S1 needs point-in-time membership at {on}")
        m = pd.Period(on, freq="M")
        mem = members.reindex(score.index).fillna(False).astype(bool) & score.notna()
        zb = winsorised_z(score[mem])
        r = res.get(m, pd.Series(dtype=float)).reindex(zb.index)
        zr = winsorised_z(r).fillna(0.0)
        out = (0.75 * zb + 0.25 * zr).reindex(score.index)
        return out

    return fn


def _window_sharpe(prices_a: np.ndarray, log_ret: np.ndarray, start: int, end: int) -> np.ndarray:
    p0, p1 = prices_a[start], prices_a[end]
    ok = np.isfinite(p0) & np.isfinite(p1) & (p0 != 0)
    lr = np.full(p0.shape, np.nan)
    lr[ok] = np.log(np.maximum(p1[ok] / p0[ok], 0.001))
    w = log_ret[start + 1: end + 1]
    n = np.isfinite(w).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sd = np.nanstd(w, axis=0, ddof=0)
        vol = sd * np.sqrt(n)
        out = lr / np.where(vol > 0, vol, np.nan)
    out[n <= 1] = np.nan
    return out


def s6_score_fn(close: pd.DataFrame, offset: int):
    """1M 10%, 3M 30%, 6M 30% as the live score, 12-7 30% (shifted month ends)."""
    from src.engine.calendar_momentum import anchor_frame, period_sharpe_at, winsorised_z

    prices = close
    log_ret = np.log(prices / prices.shift(1).replace(0, np.nan))
    anchor = anchor_frame(prices)
    anchor_a, lr_a = anchor.to_numpy(dtype=float), log_ret.to_numpy(dtype=float)
    ends = signal_rows(prices.index, offset)
    pos = {d: i for i, d in enumerate(prices.index)}

    def fn(on, score, members):
        idx = pos[pd.Timestamp(on)]
        m = pd.Period(on, freq="M")
        comp = pd.Series(0.0, index=prices.columns)
        avail = pd.Series(0.0, index=prices.columns)
        for months, wt in ((1, 0.10), (3, 0.30), (6, 0.30)):
            raw, _ = period_sharpe_at(prices, log_ret, idx, months, prices_anchor=anchor)
            z = winsorised_z(raw)
            comp += z.fillna(0.0) * wt
            avail += z.notna().astype(float) * wt
        if (m - 12) in ends.index and int(ends[m - 12]) >= 0:
            raw = pd.Series(_window_sharpe(anchor_a, lr_a, int(ends[m - 12]), int(ends[m - 6])),
                            index=prices.columns)
            z = winsorised_z(raw)
            comp += z.fillna(0.0) * 0.30
            avail += z.notna().astype(float) * 0.30
        return comp.div(avail.replace(0.0, np.nan)).reindex(score.index)

    return fn


def shares_proxy(close: pd.DataFrame) -> tuple[pd.Series, str]:
    from src.core.config import REPO_MCAP_FILE

    mc = pd.read_csv(REPO_MCAP_FILE, dtype={"Symbol": str})
    as_of = pd.to_datetime(mc["AsOf"]).max()
    row = close.ffill(limit=5).loc[:as_of].iloc[-1]
    cap = pd.Series(pd.to_numeric(mc["MarketCap"], errors="coerce").to_numpy(), index=mc["Symbol"])
    cap = cap[~cap.index.duplicated()]
    return (cap / row.reindex(cap.index)).replace([np.inf, -np.inf], np.nan).dropna(), str(as_of.date())


def s4_cells(close: pd.DataFrame, volume: pd.DataFrame, membership: dict, offset: int,
             shares: pd.Series) -> pd.DataFrame:
    """Per signal: +1 low return / high turnover (blocked), 0 other cell, NaN unsorted."""
    from src.engine.membership import members_on

    rows = signal_rows(close.index, offset)
    cf = close.ffill(limit=5)
    sh = shares.reindex(close.columns)
    out = {}
    vol_cs = volume.fillna(0.0).cumsum()
    for m in rows.index[1:]:
        s, p = int(rows[m]), int(rows[m - 1]) if (m - 1) in rows.index else -1
        if p < 0 or s <= p:
            continue
        d = close.index[s]
        mem = members_on(membership, d.date(), canonical=True)
        if mem is None:
            continue
        cols = close.columns[close.columns.isin(list(mem))]
        r = cf.iloc[s][cols] / cf.iloc[p][cols] - 1.0
        to = (vol_cs.iloc[s][cols] - vol_cs.iloc[p][cols]) / sh[cols]
        ok = r.notna() & to.notna() & (to > 0)
        r, to = r[ok], to[ok]
        cell = pd.Series(np.nan, index=close.columns)
        if len(r) >= 4:
            low = r < r.median()
            high = to > to.median()
            cell[r.index] = (low & high).astype(float)
        out[d] = cell
    return pd.DataFrame(out).T


def mad_values(close: pd.DataFrame) -> pd.DataFrame:
    p = close.ffill()
    mad = p.rolling(21).mean() / p.rolling(200).mean()
    enough = close.notna().cumsum() >= 200
    return mad.where(enough, np.inf).where(close.ffill().notna())


# ── run ──────────────────────────────────────────────────────────────────────

_INP: dict | None = None
_CACHE: dict = {}


def _init_worker(extra_path: str | None) -> None:
    global _INP
    logging.disable(logging.WARNING)
    _INP = load_inputs(extra_path)
    _INP.update(schedule(_INP))


def _french():
    if "fr" not in _CACHE:
        _CACHE["fr"] = load_french()
    return _CACHE["fr"]


def _res():
    if "res" not in _CACHE:
        _CACHE["res"] = residual_scores(_INP["close"], _french()["ff3_m"])
    return _CACHE["res"]


def _industry_gate():
    if "ind" not in _CACHE:
        from src.engine import filters
        _CACHE["ind"] = filters.industry_momentum(_INP["close"], _INP["sector_map"]).attrs["rank"] > 0.5
    return _CACHE["ind"]


def variant_kwargs(name: str, offset: int) -> dict:
    inp = _INP
    if name == "base":
        return {}
    if name == "S1":
        return dict(_research_score=s1_score_fn(_res()))
    if name == "C2":
        return dict(_research_score=s1_score_fn(_res()), _research_gate=_industry_gate(), research_gate_on="buy")
    if name == "S6":
        return dict(_research_score=s6_score_fn(inp["close"], offset))
    if name == "S7":
        if "mad" not in _CACHE:
            _CACHE["mad"] = mad_values(inp["close"])
        return dict(_research_values=_CACHE["mad"], research_drop=0.2, research_gate_on="buy")
    if name == "S4":
        if "shares" not in _CACHE:
            _CACHE["shares"] = shares_proxy(inp["close"])[0]
        cells = s4_cells(inp["close"], inp["volume"], inp["membership"], offset, _CACHE["shares"])
        gate = cells.fillna(0.0) < 0.5                # True = may buy
        return dict(_research_gate=gate, research_gate_on="buy")
    raise KeyError(name)


def base_kwargs(cost: float) -> dict:
    kw = live_kwargs()
    kw.update(cost_bps=float(cost), members_only_scoring_from=None, ema_warmup_from=None,
              hold_cap=None, hold_cap_from=None, buy_size=None, weight_reset_months=None)
    return kw


def run_label(name: str, offset: int, cost: float) -> str:
    return f"{name}_o{offset}_c{int(cost)}"


def _run_one(name: str, offset: int, cost: float, out: str) -> tuple[str, float]:
    from src.engine.backtester import run_backtest

    t0 = time.perf_counter()
    inp = _INP
    label = run_label(name, offset, cost)
    hs = inp["history_start"][offset]
    months = (inp["end_month"] - pd.Period(hs, freq="M")).n + 1
    extra = variant_kwargs(name, offset)
    raw = inspect.unwrap(run_backtest)
    res = raw(f"prereg-{label}", inp["close"], _benchmark_close=inp["spy"], sector_map=inp["sector_map"],
              _membership=inp["membership"], backtest_months=months, stateful_history=True,
              history_start=hs, _actions=[], signal_offset=int(offset),
              research_label=f"prereg-{label}", **base_kwargs(cost), **extra)
    if not res or not res.get("stats"):
        raise RuntimeError(f"{label}: no result")
    runs = Path(out) / "runs"
    eq = res["equity_curve"]
    eq.pct_change().iloc[1:].rename("net").to_frame().to_parquet(runs / f"{label}.parquet")
    m = res["monthly"][["Period Start", "Period End", "Turnover %", "Holdings", "Buys", "Sells"]].copy()
    m.to_parquet(runs / f"{label}.monthly.parquet")
    stats = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else str(v))
             for k, v in res["stats"].items() if not isinstance(v, (list, dict))}
    (runs / f"{label}.json").write_text(json.dumps({"label": label, "base_date": str(eq.index[0].date()),
                                                   "stats": stats}))
    return label, time.perf_counter() - t0


def _extra_arg(args) -> str | None:
    if getattr(args, "no_extra", False):
        return None
    if args.extra_prices:
        return args.extra_prices
    return str(DEFAULT_EXTRA) if DEFAULT_EXTRA.exists() else None


def cmd_params(args) -> None:
    fr = load_french()
    print(json.dumps({"vintage": fr["vintage"], "S3": dm_parameters(fr)}, indent=2))


def cmd_checks(args) -> None:
    logging.disable(logging.WARNING)
    extra = _extra_arg(args)
    inp = load_inputs(extra)
    sch = schedule(inp)
    print(json.dumps(section2(inp, sch), indent=2, default=str))


def section2(inp: dict, sch: dict) -> dict:
    from src.engine.membership import members_on
    from src.loaders import price_store as ps

    out: dict = {}
    vol = ps.read_wide(["Close", "Volume"], start="2014-05-01", symbols=["AAPL", "NVDA"])
    checks = []
    for sym, day, ratio in (("AAPL", "2014-06-09", 7), ("AAPL", "2020-08-31", 4), ("NVDA", "2024-06-10", 10)):
        v = vol["Volume"][sym]
        i = v.index.get_loc(pd.Timestamp(day))
        before, after = float(v.iloc[i - 20:i].median()), float(v.iloc[i:i + 20].median())
        checks.append({"symbol": sym, "split": day, "ratio": ratio, "median_vol_20_before": before,
                       "median_vol_20_after": after, "after_over_before": after / before,
                       "split_adjusted": bool(after / before < ratio / 2)})
    out["volume_split_check"] = checks
    hist = inp["membership"]
    out["membership_baseline"] = hist["baseline"]["date"]
    out["membership_changes"] = len(hist.get("changes") or [])
    out["price_first_session"] = str(inp["close"].index[0].date())
    out["first_monthly_return"] = str(pd.Period(inp["close"].index[0], freq="M") + 1)
    out["m0"] = str(sch["m0"])
    out["history_start"] = {o: str(d.date()) for o, d in sch["history_start"].items()}
    out["common_first_fill_d0"] = str(sch["d0"].date())
    out["end_month"] = str(inp["end_month"])
    out["end_date"] = str(inp["end_date"].date())
    # Former members (ever in the timeline from its baseline) with no price at all.
    cols = set(inp["close"].columns)
    ever = set(inp["ever"])
    today = members_on(hist, inp["end_date"].date(), canonical=True) or set()
    former = ever - today
    out["ever_members"] = len(ever)
    out["former_members"] = len(former)
    out["former_without_any_price"] = len(former - cols)
    out["former_without_any_price_list"] = sorted(former - cols)
    out["extra_symbols_added"] = len(inp["extra_added"])
    out["coverage"] = coverage(inp, sch["m0"], cols)
    if inp["extra_added"]:
        out["coverage_store_only"] = coverage(inp, sch["m0"], set(inp["store_cols"]))
    out["coverage_2020_on_store_only"] = coverage(inp, pd.Period("2020-01", "M"),
                                                  set(inp["store_cols"]))["share"]
    sec = inp["sector_map"]
    out["symbols_with_sector_Other"] = sum(1 for c in cols if sec.get(c, "Other") == "Other")
    return out


def cmd_run(args) -> None:
    out = Path(args.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    extra = _extra_arg(args)
    logging.disable(logging.WARNING)
    inp = load_inputs(extra)
    sch = schedule(inp)
    fr = load_french()
    meta = {"extra_prices": extra, "section2": section2(inp, sch), "french_vintage": fr["vintage"],
            "S3": dm_parameters(fr), "symbols": int(inp["close"].shape[1]),
            "last_session_loaded": str(inp["close"].index[-1].date()),
            "base_kwargs": {k: (list(v) if isinstance(v, tuple) else v) for k, v in base_kwargs(10).items()},
            "choices": CHOICES, "run_date": pd.Timestamp.now().isoformat(timespec="seconds")}
    sh, sh_asof = shares_proxy(inp["close"])
    meta["s4_shares_asof"] = sh_asof
    meta["s4_proxy_check"] = s4_proxy_check(inp, sh)
    (out / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    s2c = meta["section2"]
    print(f"m0 {s2c['m0']}, d0 {s2c['common_first_fill_d0']}, end {s2c['end_date']}; "
          f"{meta['symbols']} symbols; coverage {s2c['coverage']['share']:.1%}", flush=True)
    del inp
    todo = [(n, o, c) for c in COSTS for n in ENGINE for o in OFFSETS
            if not (out / "runs" / f"{run_label(n, o, c)}.json").exists()]
    if args.only:
        keep = set(args.only.split(","))
        todo = [t for t in todo if t[0] in keep]
    print(f"{len(todo)} runs to do, {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers, initializer=_init_worker, initargs=(extra,)) as pool:
        futs = {pool.submit(_run_one, n, o, c, str(out)): (n, o, c) for n, o, c in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            n, o, c = futs[fut]
            try:
                lab, secs = fut.result()
                print(f"[{i}/{len(todo)}] {lab} in {secs:.0f}s ({(time.perf_counter() - t0) / 60:.1f} min)",
                      flush=True)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                print(f"[{i}/{len(todo)}] {run_label(n, o, c)} FAILED: {type(exc).__name__}: {exc}", flush=True)


def s4_proxy_check(inp: dict, shares: pd.Series) -> dict:
    """Section 7 S4: how often a member's cell changes in 2011 if its shares were 30% higher."""
    cells = s4_cells(inp["close"], inp["volume"], inp["membership"], 0, shares)
    from src.engine.membership import members_on

    rows = signal_rows(inp["close"].index, 0)
    cf, vcs = inp["close"].ffill(limit=5), inp["volume"].fillna(0.0).cumsum()
    flips = total = 0
    for m in pd.period_range("2011-01", "2011-12", freq="M"):
        s, p = int(rows[m]), int(rows[m - 1])
        d = inp["close"].index[s]
        mem = members_on(inp["membership"], d.date(), canonical=True) or set()
        cols = inp["close"].columns[inp["close"].columns.isin(list(mem))]
        r = cf.iloc[s][cols] / cf.iloc[p][cols] - 1.0
        to = (vcs.iloc[s][cols] - vcs.iloc[p][cols]) / shares.reindex(cols)
        ok = r.notna() & to.notna() & (to > 0)
        r, to = r[ok], to[ok]
        med_r, med_t = r.median(), to.median()
        base = (r < med_r) & (to > med_t)
        shifted = (r < med_r) & (to / 1.3 > med_t)       # that name alone with 30% more shares
        flips += int((base != shifted).sum())
        total += int(len(r))
    sorted_share = float(cells.loc["2011"].notna().sum(axis=1).mean()) if len(cells.loc["2011"]) else 0.0
    return {"member_months_2011": total, "cell_changes_if_shares_30pct_higher": flips,
            "share_changed": flips / total if total else float("nan"),
            "mean_members_sorted_per_month_2011": sorted_share,
            "note": "No share-count history in the store: the buyback/issuance names were not checked "
                    "against dated share counts."}


# ── statistics ───────────────────────────────────────────────────────────────

def _cagr(r: np.ndarray) -> np.ndarray:
    return np.prod(1.0 + r, axis=0) ** (TRADING_DAYS / max(len(r), 1)) - 1.0


def _sharpe(r: np.ndarray, rf: np.ndarray) -> np.ndarray:
    x = r - rf[:, None]
    sd = x.std(axis=0, ddof=1)
    return x.mean(axis=0) / np.where(sd > 0, sd, np.nan) * math.sqrt(TRADING_DAYS)


def _metrics(r: np.ndarray, rf: np.ndarray) -> dict[str, np.ndarray]:
    return {"cagr": _cagr(r), "sharpe": _sharpe(r, rf), "mdd": max_drawdown(r)}


def overlay(book: pd.Series, monthly: pd.DataFrame, spy_r: pd.Series, weight_of, cost_bps: float,
            dates: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Book scaled by w at each fill, the rest in SPY; returns (daily, turnover % per fill, w per fill)."""
    c = cost_bps / 10000.0
    fills = pd.to_datetime(monthly["Period Start"]).tolist()
    turns = monthly["Turnover %"].to_numpy(dtype=float)
    pos = {d: i for i, d in enumerate(dates)}
    out = pd.Series(np.nan, index=book.index)
    w_prev = None
    tv, ws = {}, {}
    fill_pos = sorted(range(len(fills)), key=lambda j: fills[j])
    for jj, j in enumerate(fill_pos):
        f = fills[j]
        sig = dates[pos[f] - 1]
        w = weight_of(pd.Period(sig, freq="M"))
        if not np.isfinite(w):
            raise RuntimeError(f"no overlay weight for the signal of {sig.date()}")
        nxt = fills[fill_pos[jj + 1]] if jj + 1 < len(fill_pos) else None
        seg = book[(book.index > f) & ((book.index <= nxt) if nxt is not None else True)]
        sr = spy_r.reindex(seg.index).fillna(0.0).to_numpy()
        cost = (1.0 - w) * c / 2.0 if w_prev is None else abs(w - w_prev) * c
        B, S, V = w, 1.0 - w, 1.0
        vals = []
        for k, rb in enumerate(seg.to_numpy()):
            B *= 1.0 + rb
            S *= 1.0 + sr[k]
            r = (B + S) / V - 1.0 - (cost if k == 0 else 0.0)
            if k == 0:                                     # the cost leaves the account pro rata
                scale = V * (1.0 + r) / (B + S)
                B, S = B * scale, S * scale
            V = B + S
            vals.append(r)
        out.loc[seg.index] = vals
        tv[f] = w * turns[j] + (abs(w - w_prev) * 100.0 if w_prev is not None else (1.0 - w) * 50.0)
        ws[f] = w
        w_prev = w
    return out.dropna(), pd.Series(tv).sort_index(), pd.Series(ws).sort_index()


def _load_runs(out: Path) -> tuple[dict, dict]:
    rets, mons = {}, {}
    for js in sorted((out / "runs").glob("*.json")):
        lab = js.stem
        rets[lab] = pd.read_parquet(js.with_suffix(".parquet"))["net"]
        mons[lab] = pd.read_parquet(out / "runs" / f"{lab}.monthly.parquet")
    return rets, mons


def build_series(out: Path, meta: dict) -> tuple[dict, dict, dict]:
    """(daily returns, turnover per fill, extras) per (variant, offset, cost) for all nine and base."""
    from src.loaders import benchmark_store

    rets, mons = _load_runs(out)
    missing = [run_label(n, o, c) for c in COSTS for n in ENGINE for o in OFFSETS
               if run_label(n, o, c) not in rets]
    if missing:
        raise SystemExit(f"{len(missing)} runs missing, e.g. {missing[:4]}; run `run` first.")
    fr = load_french()
    dm = dm_inputs(fr)
    par = meta["S3"]
    spy = pd.to_numeric(benchmark_store.history("max", "SPY_TR"), errors="coerce").dropna()
    any_ret = rets[run_label("base", 0, 10)]
    cal = spy.index.union(any_ret.index)
    spy_r = spy.reindex(cal).ffill().pct_change(fill_method=None)
    dates = pd.DatetimeIndex(sorted(set(spy.index) | set().union(*[set(r.index) for r in rets.values()])))
    # The price calendar (sessions); the fills' previous session is the signal.
    cal_idx = dates
    w_s2 = {}

    def wt(kind):
        def f(m):
            key = (kind, m)
            if key not in w_s2:
                w_s2[key] = (s2_weight(fr["umd_d"], m - 1) if kind == "S2" else
                             s2_weight(fr["umd_d"], m - 1, downside=True) if kind == "S2d" else
                             s3_weight(dm, par, m))
            return w_s2[key]
        return f

    series, turn, extras = {}, {}, {"weights": {}}
    for c in COSTS:
        for o in OFFSETS:
            for n in ENGINE:
                lab = run_label(n, o, c)
                series[(n, o, c)] = rets[lab]
                turn[(n, o, c)] = pd.Series(mons[lab]["Turnover %"].to_numpy(dtype=float),
                                            index=pd.to_datetime(mons[lab]["Period Start"]))
            for n, src, kind in (("S2", "base", "S2"), ("S3", "base", "S3"), ("C1", "S1", "S2"),
                                 ("S2d", "base", "S2d")):
                lab = run_label(src, o, c)
                r, tv, ws = overlay(rets[lab], mons[lab], spy_r, wt(kind), c, cal_idx)
                series[(n, o, c)], turn[(n, o, c)] = r, tv
                extras["weights"][(n, o, c)] = ws
    return series, turn, {"spy_r": spy_r, "rf": fr["ff3_d"]["RF"], **extras}


def tranche(series: dict, turn: dict, cost: float, start: pd.Timestamp) -> tuple[pd.Series, pd.Series]:
    parts = []
    for o in OFFSETS:
        r = series[("base", o, cost)]
        parts.append((1.0 + r[r.index > start]).cumprod())
    eq = pd.concat(parts, axis=1).dropna()
    total = eq.mean(axis=1)
    daily = total.pct_change()
    daily.iloc[0] = total.iloc[0] - 1.0
    tv = pd.concat([turn[("base", o, cost)] / 4.0 for o in OFFSETS]).sort_index()
    return daily, tv


def sample_stats(series: dict, turn: dict, ex: dict, start: pd.Timestamp, end: pd.Timestamp,
                 primary_start: pd.Timestamp, cost: float) -> dict:
    """All statistics for one sample and cost."""
    names = ["base", *SHORTLIST, "S2d"]
    cols, keys = [], []
    s5, s5_tv = tranche(series, turn, cost, primary_start)
    for n in names:
        for o in OFFSETS:
            s = s5 if n == "S5" else series[(n, o, cost)]
            cols.append(s)
            keys.append((n, o))
    R = pd.concat(cols, axis=1, keys=range(len(cols)))
    R = R[(R.index > start) & (R.index <= end)]
    if R.isna().any().any():
        bad = R.columns[R.isna().any()].tolist()
        raise RuntimeError(f"series with gaps in the sample: {[keys[b] for b in bad][:6]}")
    rf = ex["rf"].reindex(R.index).ffill().fillna(ex["rf"].iloc[-1]).to_numpy()
    spy = ex["spy_r"].reindex(R.index).fillna(0.0).to_numpy()
    X = R.to_numpy()
    T = len(X)
    years = T / TRADING_DAYS
    col = {k: i for i, k in enumerate(keys)}

    met = _metrics(X, rf)
    vol = X.std(axis=0, ddof=1) * math.sqrt(TRADING_DAYS)
    act = X - spy[:, None]
    te = act.std(axis=0, ddof=1) * math.sqrt(TRADING_DAYS)
    ir = act.mean(axis=0) * TRADING_DAYS / np.where(te > 0, te, np.nan)
    tov = {}
    for n, o in keys:
        tv = s5_tv if n == "S5" else turn[(n, o, cost)]
        tov[(n, o)] = float(tv[(tv.index >= start) & (tv.index < end)].sum() / years)
    half = T // 2
    mh = [_metrics(X[:half], rf[:half]), _metrics(X[half:], rf[half:])]

    rng = np.random.default_rng(SEED)
    boot = {m: np.empty((N_DRAWS, X.shape[1])) for m in ("cagr", "sharpe", "mdd")}
    for i in range(N_DRAWS):
        ix = block_indices(T, BLOCK, rng)
        mi = _metrics(X[ix], rf[ix])
        for m in boot:
            boot[m][i] = mi[m]

    def gap(arr, n, against="base"):
        return np.mean([arr[..., col[(n, o)]] - arr[..., col[(against, o)]] for o in OFFSETS], axis=0)

    rows = {}
    for n in names:
        row = {"cagr": float(np.mean([met["cagr"][col[(n, o)]] for o in OFFSETS])),
               "mdd": float(np.mean([met["mdd"][col[(n, o)]] for o in OFFSETS])),
               "vol": float(np.mean([vol[col[(n, o)]] for o in OFFSETS])),
               "sharpe": float(np.mean([met["sharpe"][col[(n, o)]] for o in OFFSETS])),
               "turnover": float(np.mean([tov[(n, o)] for o in OFFSETS])),
               "te": float(np.mean([te[col[(n, o)]] for o in OFFSETS])),
               "ir": float(np.mean([ir[col[(n, o)]] for o in OFFSETS])),
               "by_offset": {o: {"cagr": float(met["cagr"][col[(n, o)]]), "mdd": float(met["mdd"][col[(n, o)]]),
                                 "sharpe": float(met["sharpe"][col[(n, o)]]), "turnover": tov[(n, o)]}
                             for o in OFFSETS}}
        if n != "base":
            for against in (["base", "S1"] if n == "C1" else ["base"]):
                g = {}
                for m in ("cagr", "sharpe", "mdd"):
                    g[m] = float(gap(met[m], n, against))
                    g[f"{m}_h1"] = float(gap(mh[0][m], n, against))
                    g[f"{m}_h2"] = float(gap(mh[1][m], n, against))
                    b = gap(boot[m], n, against)
                    g[f"{m}_lo"], g[f"{m}_hi"] = float(np.percentile(b, 5)), float(np.percentile(b, 95))
                    g[f"{m}_p"] = float((b > 0).mean())
                    g[f"{m}_by_offset"] = {o: float(met[m][col[(n, o)]] - met[m][col[(against, o)]])
                                           for o in OFFSETS}
                g["turnover"] = float(np.mean([tov[(n, o)] - tov[(against, o)] for o in OFFSETS]))
                row["vs_" + against] = g
        rows[n] = row
    base_cagrs = [met["cagr"][col[("base", o)]] for o in OFFSETS]
    s5 = X[:, col[("S5", 0)]]
    rtl = [float((X[:, col[("base", o)]] - s5).std(ddof=1) * math.sqrt(TRADING_DAYS)) for o in OFFSETS]
    rows["S5"]["dispersion"] = {
        "base_sd": float(np.std(base_cagrs, ddof=1)), "base_range": float(np.ptp(base_cagrs)),
        "tranched_sd": 0.0, "cagr_gap_vs_mean_base": float(met["cagr"][col[("S5", 0)]] - np.mean(base_cagrs)),
        "cagr_gap_h1": float(mh[0]["cagr"][col[("S5", 0)]] - np.mean([mh[0]["cagr"][col[("base", o)]]
                                                                     for o in OFFSETS])),
        "cagr_gap_h2": float(mh[1]["cagr"][col[("S5", 0)]] - np.mean([mh[1]["cagr"][col[("base", o)]]
                                                                     for o in OFFSETS])),
        "rtl_by_offset": dict(zip(OFFSETS, rtl)), "rtl_mean": float(np.mean(rtl))}
    return {"rows": rows, "sessions": T, "first": str(R.index[0].date()), "last": str(R.index[-1].date()),
            "half_split": str(R.index[half].date())}


PRIMARY = {"selection": "cagr", "overlay": "sharpe"}


def verdict(n: str, st10: dict, st20: dict) -> tuple[str, list[str]]:
    row = st10["rows"][n]
    if n == "S5":
        d = row["dispersion"]
        d20 = st20["rows"]["S5"]["dispersion"]
        ok = d["tranched_sd"] <= d["base_sd"] * (2 / 3) and d["cagr_gap_vs_mean_base"] >= -0.005
        why = [f"base dispersion {d['base_sd']:.4f}, tranched 0 (by construction)",
               f"CAGR gap vs mean base {d['cagr_gap_vs_mean_base'] * 100:+.2f} pt (20 bps "
               f"{d20['cagr_gap_vs_mean_base'] * 100:+.2f})"]
        if ok:
            return "pass", why
        if d["cagr_gap_h1"] < -0.005 and d["cagr_gap_h2"] < -0.005:
            return "reject", why
        return "inconclusive", why
    g, g20 = row["vs_base"], st20["rows"][n]["vs_base"]
    m = PRIMARY[KIND[n]]
    fails = []
    if not (g[f"{m}_h1"] > 0 and g[f"{m}_h2"] > 0):
        fails.append("halves")
    if not g[f"{m}_p"] >= 0.90:
        fails.append(f"bootstrap {g[f'{m}_p']:.0%} < 90%")
    if not all(v > 0 for v in g[f"{m}_by_offset"].values()):
        fails.append("not ahead at every offset")
    if not g20[m] > 0:
        fails.append("not ahead at 20 bps")
    if not g["mdd"] >= -0.02:
        fails.append("max drawdown > 2 pts worse")
    if not g["turnover"] <= 15.0:
        fails.append("turnover > 15 pts higher")
    if not fails:
        return "pass", []
    if (g[f"{m}_h1"] < 0 and g[f"{m}_h2"] < 0) or g[f"{m}_p"] <= 0.20:
        return "reject", fails
    return "inconclusive", fails


def cmd_report(args) -> None:
    out = Path(args.out)
    meta = json.loads((out / "meta.json").read_text())
    s2 = meta["section2"]
    series, turn, ex = build_series(out, meta)
    d0 = pd.Timestamp(s2["common_first_fill_d0"])
    end = pd.Timestamp(s2["end_date"])
    samples = {"primary": d0, "secondary": max(pd.Timestamp(SECONDARY_START) - pd.Timedelta(days=1), d0)}
    results = {}
    for sname, start in samples.items():
        results[sname] = {c: sample_stats(series, turn, ex, start, end, d0, c) for c in COSTS}
    verdicts = {s: {n: verdict(n, results[s][10.0], results[s][20.0]) for n in SHORTLIST} for s in results}
    w = ex["weights"]
    wstats = {}
    for n in ("S2", "S3", "C1", "S2d"):
        ws = pd.concat([w[(n, o, 10.0)] for o in OFFSETS])
        ws = ws[(ws.index >= d0) & (ws.index <= end)]
        wstats[n] = {"mean": float(ws.mean()), "min": float(ws.min()), "share_below_1": float((ws < 1).mean())}

    pct = lambda v: f"{v * 100:+.2f}"  # noqa: E731
    L = [f"# Pre-registered momentum study: results ({meta['run_date'][:10]})", "",
         f"Prices: store{' + extra research prices (' + str(s2['extra_symbols_added']) + ' symbols)' if meta['extra_prices'] else ' only'}; "
         f"{meta['symbols']} symbols. Membership: S&P 500 point in time from {s2['membership_baseline']} "
         f"({s2['membership_changes']} changes). Member-months with a price (signals {s2['m0']} to "
         f"{s2['end_month']}): {s2['coverage']['with_price']}/{s2['coverage']['member_months']} = "
         f"{s2['coverage']['share']:.1%}" + (f" (store alone {s2['coverage_store_only']['share']:.1%})"
                                             if 'coverage_store_only' in s2 else "") + ". "
         f"French vintage {next(iter(meta['french_vintage'].values()))['vintage']}. "
         f"S3: gamma0 {meta['S3']['gamma0']:.5f}, gamma1 {meta['S3']['gamma1']:.3f}, kappa {meta['S3']['kappa']:.5f}.", ""]
    for sname in results:
        st = results[sname][10.0]
        b = st["rows"]["base"]
        L += [f"## {sname.title()} sample: {st['first']} to {st['last']} ({st['sessions']} sessions, "
              f"halves split at {st['half_split']})", "",
              f"Base book (mean of four offsets, 10 bps): CAGR {b['cagr']:.2%}, max drawdown {b['mdd']:.2%}, "
              f"Sharpe {b['sharpe']:.2f}, volatility {b['vol']:.1%}, turnover {b['turnover']:.0f}% a year, "
              f"TE {b['te']:.1%}, IR {b['ir']:.2f}. By offset (CAGR / MDD / Sharpe): "
              + "; ".join(f"{o}: {v['cagr']:.2%} / {v['mdd']:.1%} / {v['sharpe']:.2f}"
                          for o, v in b["by_offset"].items()) + ".", ""]
        for c in COSTS:
            st = results[sname][c]
            L += [f"### {int(c)} bps", "",
                  "| Variant | Primary | CAGR | MDD | Sharpe | Turn./yr | TE | IR | Primary gap (90% range) | "
                  "ahead in | H1 / H2 | by offset 0/5/10/15 | ΔCAGR | ΔSharpe | ΔMDD | ΔTurn. | Verdict |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for n in [*SHORTLIST, "S2d"]:
                r = st["rows"][n]
                if n == "S5":
                    d = r["dispersion"]
                    vv = verdicts[sname]["S5"][0] if c == 10.0 else "—"
                    L.append(f"| S5 | dispersion | {r['cagr']:.2%} | {r['mdd']:.1%} | {r['sharpe']:.2f} | "
                             f"{r['turnover']:.0f} | {r['te']:.1%} | {r['ir']:.2f} | base sd {d['base_sd'] * 100:.2f} pt "
                             f"(range {d['base_range'] * 100:.2f}); tranched 0 | — | CAGR vs mean base "
                             f"{pct(d['cagr_gap_h1'])} / {pct(d['cagr_gap_h2'])} | RTL {d['rtl_mean'] * 100:.2f} pt | "
                             f"{pct(d['cagr_gap_vs_mean_base'])} | {r['vs_base']['sharpe']:+.3f} | "
                             f"{pct(r['vs_base']['mdd'])} | {r['vs_base']['turnover']:+.1f} | {vv} |")
                    continue
                m = "sharpe" if n == "S2d" else PRIMARY[KIND[n]]
                for against in (["base", "S1"] if n == "C1" else ["base"]):
                    g = r["vs_" + against]
                    f = (lambda v: f"{v:+.3f}") if m == "sharpe" else pct
                    vv = (verdicts[sname][n][0] if (c == 10.0 and against == "base" and n != "S2d")
                          else ("robustness" if n == "S2d" else "—"))
                    L.append(
                        f"| {n}{'' if against == 'base' else ' vs S1'} | {m} | {r['cagr']:.2%} | {r['mdd']:.1%} | "
                        f"{r['sharpe']:.2f} | {r['turnover']:.0f} | {r['te']:.1%} | {r['ir']:.2f} | "
                        f"{f(g[m])} ({f(g[m + '_lo'])} to {f(g[m + '_hi'])}) | {g[m + '_p']:.0%} | "
                        f"{f(g[m + '_h1'])} / {f(g[m + '_h2'])} | "
                        f"{' / '.join(f(v) for v in g[m + '_by_offset'].values())} | {pct(g['cagr'])} | "
                        f"{g['sharpe']:+.3f} | {pct(g['mdd'])} | {g['turnover']:+.1f} | {vv} |")
            L.append("")
        L += [f"### Verdicts ({sname})", ""]
        for n in SHORTLIST:
            v, why = verdicts[sname][n]
            L.append(f"- **{n}** ({TEXT[n]}): **{v}**" + (f" ({'; '.join(why)})" if why else ""))
        L.append("")
    L += ["## Overlay weights (fills in the primary sample, all offsets)", ""]
    L += [f"- {n}: mean {v['mean']:.2f}, lowest {v['min']:.2f}, below 1 at {v['share_below_1']:.0%} of fills"
          for n, v in wstats.items()]
    L += ["", "## Interpretation choices (fixed before the first run)", ""] + [f"- {c}" for c in meta["choices"]]
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "results.json").write_text(json.dumps(
        {"results": {s: {str(int(c)): v for c, v in d.items()} for s, d in results.items()},
         "verdicts": verdicts, "weights": wstats}, indent=1, default=str))
    print("\n".join(L))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("params")
    for name in ("checks", "run"):
        sp = sub.add_parser(name)
        sp.add_argument("--extra-prices", default=None,
                        help=f"research-only long parquet (default: {DEFAULT_EXTRA} if it exists)")
        sp.add_argument("--no-extra", action="store_true", help="the store alone, even if the file exists")
        if name == "run":
            sp.add_argument("--out", required=True)
            sp.add_argument("--workers", type=int, default=3)
            sp.add_argument("--only", default="", help="comma-separated engine variants")
    rp = sub.add_parser("report")
    rp.add_argument("--out", required=True)
    args = p.parse_args()
    {"params": cmd_params, "checks": cmd_checks, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
