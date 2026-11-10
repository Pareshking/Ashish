#!/usr/bin/env python3
"""Do additional momentum filters improve the live book? (owner, 10 Nov 2026)

    python scripts/research_filters.py run --out DIR [--workers 4] [--membership PATH]
    python scripts/research_filters.py report --out DIR

`run` backtests the live configuration (track_record.TRACK_RECORD_CONFIG: top
20 of the qualified, keep while in the top 40, above the 50-day EMA, within
20% of the 52-week high, 5% stock cap, 40% GICS-sector cap, monthly, 10 bps)
from January 2020 to the last completed month, once as it is and once with
each filter of src/engine/filters.py added through run_backtest's research
keywords. Nothing else changes; the score is the live score in every run.
About 10 s a run; ~30 runs. Each run's daily net returns and monthly table are
saved, so a stopped run resumes.

`report` compares every variant with the live run on the same sessions:

  1. the whole sample: a year, max drawdown, Sharpe (risk-free 4%), turnover;
  2. halves: the same differences in the first and second half of the sessions,
     and whether they agree in sign;
  3. a paired block bootstrap (63-session blocks, 2,000 draws; turnover on
     3-month blocks of the monthly table): 90% ranges of the difference in a
     year's return, max drawdown and turnover, and the share of draws better;
  4. walk-forward by family: each year from 2022, keep whichever of {live,
     the family's variants} had the best Sharpe on all earlier sessions, apply
     it that year; chained, against live.

A verdict per variant, by rules fixed before the numbers were seen:
  shadow   both halves ahead on a year's return, ahead in at least 80% of the
           draws, max drawdown no more than 2 pts worse, and its family's
           walk-forward not behind live;
  reject   both halves behind, or ahead in at most 20% of the draws;
  inconclusive otherwise.
"shadow" means worth recording forward beside the live book, never trading.

MEMBERSHIP BASIS. Every result is labelled with it. With
data/membership_history.json's baseline at its first snapshot (10 Nov 2026),
every month before it is scored on TODAY's S&P 1500 list: survivorship-biased
(docs/DATA_CORRECTNESS.md: on that list the score's top-minus-bottom spread
averaged -0.76 pts a month against +0.31 for French's UMD). Pass
``--membership`` a point-in-time file (baseline 2019-12-31 or earlier) to
rerun on it; members that have left are loaded from the price store when it
has them and counted when it does not.
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

TRADING_DAYS = 252
RISK_FREE = 0.04
START = "2020-01"          # owner: backtests start no earlier than 2020
WARM_START = "2019-01"     # the volatility overlay's estimate only; never reported
FIRST_WF_YEAR = 2022


# ── inputs ───────────────────────────────────────────────────────────────────

def load_inputs(membership_path: str | None = None, start: str = START) -> dict:
    from src.engine import membership as mship
    from src.engine.model_record import record_sector_map
    from src.loaders import benchmark_store, price_source
    from src.loaders.indices_loader import fetch_indices_data

    path = Path(membership_path) if membership_path else mship.HISTORY_PATH
    history = mship.load_history(path)
    if not history.get("baseline"):
        history = None
    today = fetch_indices_data()["Symbol"].tolist()
    ever = set(today)
    if history:
        ever |= set(history["baseline"]["symbols"])
        for c in history.get("changes") or []:
            ever |= set(c.get("added") or [])
    _frames, deep = price_source.load(sorted(ever))
    if deep is None:
        raise SystemExit("The price store cannot reach the 12-month lookback.")
    last = pd.Period(deep.index[-1], freq="M") - 1          # last completed month
    deep = deep.loc[: last.end_time]
    bench = benchmark_store.history("max", "SPTM_TR")
    bench = pd.to_numeric(bench, errors="coerce").dropna().loc[: deep.index[-1]]
    first_pit = pd.Timestamp(history["baseline"]["date"]) if history else None
    s0 = pd.Period(start, freq="M")
    if first_pit is None or first_pit > s0.start_time:
        basis = ("TODAY'S LIST before " + (f"{first_pit:%d %b %Y}" if first_pit else "any snapshot")
                 + " (survivorship-biased)")
    else:
        basis = f"point in time from {first_pit:%d %b %Y}"
    return {
        "close": deep, "benchmark": bench, "membership": history,
        "sector_map": record_sector_map(deep.columns),
        "end": last, "basis": basis, "membership_file": str(path),
        "missing_prices": sorted(ever - set(deep.columns)),
        "baseline": history["baseline"]["date"] if history else None,
        "changes": len(history.get("changes") or []) if history else 0,
    }


def live_kwargs() -> dict:
    """run_backtest keywords of the live record (TRACK_RECORD_CONFIG)."""
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg

    return dict(
        top_n=cfg["top_n"], rebal_freq=cfg["rebal_freq"], ema_period=cfg["ema_period"],
        high_pct=cfg["high_pct"], weight_method=cfg["weight_method"],
        config_weights=tuple(cfg["config_weights"]), cost_bps=cfg["cost_bps"],
        buffer_n=cfg["buffer_n"], members_only_scoring_from=cfg.get("members_only_scoring_from"),
        ema_warmup_from=cfg.get("ema_warmup_from"), hold_cap=cfg.get("hold_cap"),
        hold_cap_from=cfg.get("hold_cap_from"), buy_size=cfg.get("buy_size"),
        weight_reset_months=tuple(cfg.get("weight_reset_months") or ()) or None,
        stock_cap=cfg["stock_cap"], sector_cap=cfg["sector_cap"],
    )


# ── the variants ─────────────────────────────────────────────────────────────
# family, description, and a builder (inputs -> extra run_backtest keywords).
# Thresholds are the sources' own where they give one (Clenow's 15% gap,
# Faber's 10 months, Daniel & Moskowitz's 24 months, Gray & Vogel's half),
# otherwise one round value, chosen before any run and not tuned.

def _f():
    from src.engine import filters
    return filters


def _drop(values, share, on="buy"):
    return dict(_research_values=values, research_drop=share, research_gate_on=on)


def _gate(frame, on="buy"):
    return dict(_research_gate=frame, research_gate_on=on)


VARIANTS: dict[str, dict] = {
    "live": dict(family="live", text="The live book", build=lambda i: {}),
    # Frog in the pan (Da, Gurun & Warachka 2014; Gray & Vogel 2016)
    "fip_pool40": dict(family="fip", text="New buys by best FIP among the top 40 (Gray & Vogel's second sort)",
                       build=lambda i: dict(_research_values=-_f().frog_in_the_pan(i["close"], 252, 21),
                                            research_pool=40)),
    "fip_drop50": dict(family="fip", text="Buy gate: not in the worse half of the qualified by FIP",
                       build=lambda i: _drop(-_f().frog_in_the_pan(i["close"], 252, 21), 0.5)),
    "fip_drop20": dict(family="fip", text="Buy gate: not in the worst 20% of the qualified by FIP",
                       build=lambda i: _drop(-_f().frog_in_the_pan(i["close"], 252, 21), 0.2)),
    "fip_drop20_both": dict(family="fip", text="Buy and keep gate: worst 20% by FIP fail",
                            build=lambda i: _drop(-_f().frog_in_the_pan(i["close"], 252, 21), 0.2, "both")),
    # 52-week high (George & Hwang 2004)
    "high90": dict(family="high52", text="Within 10% of the 52-week high (live: 20%)",
                   build=lambda i: dict(high_pct=0.90)),
    "gh_pool40": dict(family="high52", text="New buys by nearness to the 52-week high among the top 40",
                      build=lambda i: dict(_research_values=_f().fifty_two_week_ratio(i["close"]),
                                           research_pool=40)),
    # Residual momentum (Blitz, Huij & Martens 2011), gate only
    "resid_drop50": dict(family="residual", text="Buy gate: not in the worse half of the qualified by residual momentum",
                         build=lambda i: _drop(_f().residual_score(i["close"], i["benchmark"]), 0.5)),
    "resid_pos": dict(family="residual", text="Buy gate: residual momentum above zero",
                      build=lambda i: _gate(_f().residual_score(i["close"], i["benchmark"]) > 0)),
    # Volatility (Barroso & Santa-Clara 2015; stock level)
    "vol_target": dict(family="volatility", text="Book scaled to its own median volatility, no leverage (overlay)",
                       build=None),
    "vol_drop20": dict(family="volatility", text="Buy gate: not among the 20% most volatile qualified (126 days)",
                       build=lambda i: _drop(-_f().realised_volatility(i["close"], 126), 0.2)),
    # Market trend and absolute momentum
    "faber10_buy": dict(family="market", text="No new buys when the S&P 1500 is below its 10-month SMA (Faber)",
                        build=lambda i: _gate(_f().faber_trend(i["benchmark"], 10, i["close"].index))),
    "faber10_cash": dict(family="market", text="All cash when the S&P 1500 is below its 10-month SMA (Faber)",
                         build=lambda i: _gate(_f().faber_trend(i["benchmark"], 10, i["close"].index), "both")),
    "sma200_buy": dict(family="market", text="No new buys when the S&P 1500 is below its 200-day SMA (Clenow)",
                       build=lambda i: _gate(_f().sma_trend(i["benchmark"], 200))),
    "absmkt_cash": dict(family="market", text="All cash when the S&P 1500's 12-month return is negative (TSMOM / dual momentum)",
                        build=lambda i: _gate(_f().absolute_trend(i["benchmark"], 252), "both")),
    "bear24_buy": dict(family="market", text="No new buys when the S&P 1500's 24-month return is negative (Daniel & Moskowitz)",
                       build=lambda i: _gate(_f().not_bear_market(i["benchmark"], 504))),
    "absstock": dict(family="absolute", text="Buy gate: the stock's own 12-month return above 4% (absolute momentum)",
                     build=lambda i: _gate(_f().period_return(i["close"], 252) > RISK_FREE)),
    # Seasonality (Heston & Sadka 2008)
    "season_drop20": dict(family="seasonality", text="Buy gate: not in the worst 20% of the qualified by same-month history",
                          build=lambda i: _drop(_f().same_month_seasonality(i["close"], 10, 5), 0.2)),
    # Short-term reversal (Jegadeesh 1990; Jegadeesh & Titman 1993)
    "str_drop10": dict(family="reversal", text="Buy gate: not in the 10% of the qualified with the highest 1-month return",
                       build=lambda i: _drop(-_f().period_return(i["close"], 21), 0.1)),
    # Lottery stocks (Bali, Cakici & Whitelaw 2011)
    "max_drop20": dict(family="max", text="Buy gate: not in the 20% of the qualified with the highest MAX (21 days)",
                       build=lambda i: _drop(-_f().max_daily_return(i["close"], 21), 0.2)),
    # Clenow, Stocks on the Move
    "gap15_buy": dict(family="clenow", text="Buy gate: no daily move beyond 15% in 90 sessions",
                      build=lambda i: _gate(_f().largest_move(i["close"], 90) <= 0.15)),
    "gap15_both": dict(family="clenow", text="Buy and keep gate: no daily move beyond 15% in 90 sessions",
                       build=lambda i: _gate(_f().largest_move(i["close"], 90) <= 0.15, "both")),
    "r2_drop20": dict(family="clenow", text="Buy gate: not in the worst 20% of the qualified by 90-day trend R-squared",
                      build=lambda i: _drop(_f().trend_r2(i["close"], 90), 0.2)),
    # Industry momentum (Moskowitz & Grinblatt 1999)
    "industry_top": dict(family="industry", text="Buy gate: the stock's GICS sector in the stronger half by 12-month return",
                         build=lambda i: _gate(_f().industry_momentum(
                             i["close"], i["sector_map"]).attrs["rank"] > 0.5)),
    # Its neighbours, added after industry_top passed, to see whether the result
    # depends on the exact rule; not candidates in their own right.
    "industry_top6m": dict(family="industry", text="As industry_top, sectors by 6-month return (neighbour)",
                           build=lambda i: _gate(_f().industry_momentum(
                               i["close"], i["sector_map"], window=126).attrs["rank"] > 0.5)),
    "industry_top_both": dict(family="industry", text="As industry_top, as a buy and keep gate (neighbour)",
                              build=lambda i: _gate(_f().industry_momentum(
                                  i["close"], i["sector_map"]).attrs["rank"] > 0.5, "both")),
}


# ── run ──────────────────────────────────────────────────────────────────────

_INPUTS: dict | None = None


def _init_worker(membership_path: str | None) -> None:
    global _INPUTS
    logging.disable(logging.WARNING)
    _INPUTS = load_inputs(membership_path)


def _backtest(name: str, extra: dict, start: str) -> dict:
    from src.engine.backtester import run_backtest

    inp = _INPUTS
    s0 = pd.Period(start, freq="M")
    months = (inp["end"] - s0).n + 1
    kw = live_kwargs()
    kw.update({k: v for k, v in extra.items() if not k.startswith("_research") and k != "research_gate_on"
               and k not in ("research_drop", "research_pool")})
    research = {k: v for k, v in extra.items() if k not in kw}
    if research:
        research["research_label"] = name
    raw = inspect.unwrap(run_backtest)
    return raw(f"filters-{name}-{start}", inp["close"], _benchmark_close=inp["benchmark"],
               sector_map=inp["sector_map"], _membership=inp["membership"], backtest_months=months,
               stateful_history=True, history_start=s0.start_time, _actions=[], **kw, **research)


def _run_one(name: str, out: str) -> tuple[str, float]:
    t0 = time.perf_counter()
    spec = VARIANTS[name]
    runs = Path(out) / "runs"
    if spec["build"] is None:                     # the overlay: the live book from 2019
        res = _backtest("live_warm", {}, WARM_START)
        name = "live_warm"
    else:
        res = _backtest(name, spec["build"](_INPUTS), START)
    if not res or not res.get("stats"):
        raise RuntimeError(f"{name}: no result")
    res["equity_curve"].pct_change().iloc[1:].rename("net").to_frame().to_parquet(runs / f"{name}.parquet")
    res["monthly"][["Period Start", "Turnover %", "Holdings", "Buys", "Sells"]].to_parquet(
        runs / f"{name}.monthly.parquet")
    stats = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else str(v))
             for k, v in res["stats"].items() if not isinstance(v, (list, dict))}
    (runs / f"{name}.json").write_text(json.dumps({"name": name, "stats": stats}))
    return name, time.perf_counter() - t0


def cmd_run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    names = list(VARIANTS) if not args.only else ["live", *[n.strip() for n in args.only.split(",")]]
    unknown = [n for n in names if n not in VARIANTS]
    if unknown:
        raise SystemExit(f"unknown variants: {', '.join(unknown)}")

    def done(n):
        return (out / "runs" / f"{'live_warm' if VARIANTS[n]['build'] is None else n}.json").exists()

    todo = [n for n in dict.fromkeys(names) if not done(n)]
    meta = load_inputs(args.membership)
    (out / "meta.json").write_text(json.dumps({
        "basis": meta["basis"], "membership_file": meta["membership_file"],
        "baseline": meta["baseline"], "changes": meta["changes"],
        "start": START, "end": str(meta["end"]), "symbols": int(meta["close"].shape[1]),
        "ever_members_without_prices": len(meta["missing_prices"]),
        "last_session": str(meta["close"].index[-1].date()), "live": {k: (list(v) if isinstance(v, tuple) else v)
                                                                       for k, v in live_kwargs().items()},
        "variants": {k: {"family": v["family"], "text": v["text"]} for k, v in VARIANTS.items()},
    }, indent=2, default=str))
    print(f"Membership basis: {meta['basis']}; {meta['close'].shape[1]} symbols; "
          f"{len(meta['missing_prices'])} ever-members without prices", flush=True)
    del meta
    print(f"{len(names)} variants, {len(todo)} to run, {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers, initializer=_init_worker, initargs=(args.membership,)) as pool:
        futures = {pool.submit(_run_one, n, str(out)): n for n in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            n = futures[fut]
            try:
                _, secs = fut.result()
                print(f"[{i}/{len(todo)}] {n} in {secs:.0f}s ({(time.perf_counter() - t0) / 60:.1f} min)",
                      flush=True)
            except Exception as exc:  # noqa: BLE001 - report and carry on
                print(f"[{i}/{len(todo)}] {n} FAILED: {type(exc).__name__}: {exc}", flush=True)


# ── statistics ───────────────────────────────────────────────────────────────

def ann_return(r: np.ndarray) -> np.ndarray:
    """Compound annual return of daily returns (columns)."""
    growth = np.prod(1.0 + r, axis=0)
    return growth ** (TRADING_DAYS / max(len(r), 1)) - 1.0


def max_drawdown(r: np.ndarray) -> np.ndarray:
    eq = np.cumprod(1.0 + r, axis=0)
    peak = np.maximum.accumulate(np.vstack([np.ones((1, r.shape[1])), eq]), axis=0)[1:]
    return (eq / peak - 1.0).min(axis=0)


def sharpe(r: np.ndarray, rf: float = RISK_FREE) -> np.ndarray:
    mu = r.mean(axis=0) * TRADING_DAYS
    sd = r.std(axis=0, ddof=1) * math.sqrt(TRADING_DAYS)
    return (mu - rf) / np.where(sd > 0, sd, np.nan)


def block_indices(t: int, block: int, rng: np.random.Generator) -> np.ndarray:
    starts = rng.integers(0, max(t - block, 1), math.ceil(t / block))
    return (starts[:, None] + np.arange(block)).ravel()[:t]


def paired_bootstrap(r: pd.DataFrame, base: str, turnover: pd.DataFrame, n: int = 2000,
                     block: int = 63, seed: int = 7) -> pd.DataFrame:
    """Each column minus ``base`` on resampled blocks of the same sessions."""
    x = r.to_numpy()
    b = list(r.columns).index(base)
    rng = np.random.default_rng(seed)
    d_ann, d_dd = np.empty((n, x.shape[1])), np.empty((n, x.shape[1]))
    for i in range(n):
        xi = x[block_indices(len(x), block, rng)]
        a, dd = ann_return(xi), max_drawdown(xi)
        d_ann[i], d_dd[i] = a - a[b], dd - dd[b]
    tv = turnover.to_numpy()
    bt = list(turnover.columns).index(base)
    d_tv = np.empty((n, tv.shape[1]))
    for i in range(n):
        ti = tv[block_indices(len(tv), 3, rng)].mean(axis=0)
        d_tv[i] = ti - ti[bt]
    obs_a, obs_d = ann_return(x), max_drawdown(x)
    obs_t = tv.mean(axis=0)
    return pd.DataFrame({
        "d_ann": obs_a - obs_a[b], "d_ann_lo": np.percentile(d_ann, 5, axis=0),
        "d_ann_hi": np.percentile(d_ann, 95, axis=0), "p_better": (d_ann > 0).mean(axis=0),
        "d_dd": obs_d - obs_d[b], "d_dd_lo": np.percentile(d_dd, 5, axis=0),
        "d_dd_hi": np.percentile(d_dd, 95, axis=0),
        "d_turn": obs_t - obs_t[bt], "d_turn_lo": np.percentile(d_tv, 5, axis=0),
        "d_turn_hi": np.percentile(d_tv, 95, axis=0),
    }, index=r.columns)


def walk_forward(r: pd.DataFrame, family_cols: list[str], first_year: int) -> pd.Series:
    """Each test year, the column of {live} + family with the best Sharpe on all earlier days."""
    parts, picks = [], {}
    for year in range(first_year, r.index[-1].year + 1):
        train = r.index < pd.Timestamp(f"{year}-01-01")
        test = (r.index >= pd.Timestamp(f"{year}-01-01")) & (r.index < pd.Timestamp(f"{year + 1}-01-01"))
        if not test.any():
            continue
        cols = ["live", *family_cols]
        s = pd.Series(sharpe(r.loc[train, cols].to_numpy()), index=cols)
        pick = str(s.idxmax())
        picks[year] = pick
        parts.append(r.loc[test, pick])
    out = pd.concat(parts)
    out.attrs["picks"] = picks
    return out


# ── report ───────────────────────────────────────────────────────────────────

def _load(out: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rets, turns = {}, {}
    for js in sorted((out / "runs").glob("*.json")):
        name = js.stem
        rets[name] = pd.read_parquet(js.with_suffix(".parquet"))["net"]
        m = pd.read_parquet(out / "runs" / f"{name}.monthly.parquet")
        turns[name] = m.set_index(pd.to_datetime(m["Period Start"]).dt.to_period("M"))["Turnover %"]
    return pd.DataFrame(rets), pd.DataFrame(turns), json.loads((out / "meta.json").read_text())


def _overlay(r_all: pd.DataFrame, t_all: pd.DataFrame, cost_bps: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    from src.engine import filters

    warm = r_all["live_warm"].dropna()
    exposure = filters.volatility_target_exposure(warm, window=126)
    scaled = filters.apply_exposure(warm, exposure, cost_bps=cost_bps)
    # Turnover: the book's own, scaled, plus the change in exposure (one way).
    e_m = exposure.groupby(exposure.index.to_period("M")).first()
    tv = (t_all["live_warm"].reindex(e_m.index) * e_m
          + e_m.diff().abs().fillna(0.0) / 2.0 * 100.0)
    return scaled, tv, exposure


def cmd_report(args: argparse.Namespace) -> None:
    out = Path(args.out)
    r_all, t_all, meta = _load(out)
    cost = float(meta["live"]["cost_bps"])
    if "live" not in r_all:
        raise SystemExit("The live run is missing; run `run` first.")
    live_idx = r_all["live"].dropna().index
    r = r_all.drop(columns=[c for c in ("live_warm",) if c in r_all]).reindex(live_idx)
    t = t_all.drop(columns=[c for c in ("live_warm",) if c in t_all])
    exposure = None
    if "live_warm" in r_all:
        scaled, tv, exposure = _overlay(r_all, t_all, cost)
        r["vol_target"] = scaled.reindex(live_idx)
        t["vol_target"] = tv.reindex(t.index)
    r = r.dropna(axis=1, how="any")
    t = t.reindex(columns=r.columns).loc[lambda d: d.index >= pd.Period(START, freq="M")].dropna(how="any")
    names = [c for c in VARIANTS if c in r.columns]
    r, t = r[names], t[names]

    x = r.to_numpy()
    full = pd.DataFrame({"ann": ann_return(x), "mdd": max_drawdown(x), "sharpe": sharpe(x),
                         "turnover": t.mean().to_numpy()}, index=names)
    half = len(r) // 2
    h1, h2 = r.iloc[:half].to_numpy(), r.iloc[half:].to_numpy()
    a1, a2 = ann_return(h1), ann_return(h2)
    li = names.index("live")
    full["d_ann_h1"], full["d_ann_h2"] = a1 - a1[li], a2 - a2[li]
    full["halves_agree"] = np.sign(full["d_ann_h1"]) == np.sign(full["d_ann_h2"])
    boot = paired_bootstrap(r, "live", t)
    full = full.join(boot)

    wf_rows = {}
    families = sorted({VARIANTS[n]["family"] for n in names} - {"live"})
    live_wf = r.loc[r.index >= pd.Timestamp(f"{FIRST_WF_YEAR}-01-01"), "live"]
    for fam in families:
        cols = [n for n in names if VARIANTS[n]["family"] == fam]
        chain = walk_forward(r, cols, FIRST_WF_YEAR)
        pair = pd.DataFrame({"wf": chain, "live": live_wf}).dropna()
        tb = pd.DataFrame(0.0, index=t.index, columns=["wf", "live"])
        wb = paired_bootstrap(pair, "live", tb).loc["wf"]
        wf_rows[fam] = {"d_ann": float(wb["d_ann"]), "lo": float(wb["d_ann_lo"]), "hi": float(wb["d_ann_hi"]),
                        "p_better": float(wb["p_better"]), "picks": chain.attrs["picks"]}

    def verdict(n: str) -> str:
        if n == "live":
            return "—"
        row = full.loc[n]
        wf = wf_rows[VARIANTS[n]["family"]]
        if (row["d_ann_h1"] > 0 and row["d_ann_h2"] > 0 and row["p_better"] >= 0.80
                and row["d_dd"] >= -0.02 and wf["d_ann"] >= 0):
            return "shadow"
        if (row["d_ann_h1"] < 0 and row["d_ann_h2"] < 0) or row["p_better"] <= 0.20:
            return "reject"
        return "inconclusive"

    full["verdict"] = [verdict(n) for n in names]

    # How often each market gate was off at a signal.
    gate_off = {}
    if any(VARIANTS[n]["family"] == "market" for n in names):
        logging.disable(logging.WARNING)
        inp = load_inputs(meta.get("membership_file"))
        sig = [d for d in inp["close"].index.to_series().groupby(inp["close"].index.to_period("M")).max()
               if d >= pd.Period(START, freq="M").start_time - pd.Timedelta(days=5)]
        for n in names:
            if VARIANTS[n]["family"] == "market":
                g = VARIANTS[n]["build"](inp)["_research_gate"].reindex(sig, method="ffill")
                gate_off[n] = [f"{d:%Y-%m}" for d, v in g.items() if not bool(v)]

    pct = lambda v: f"{v * 100:+.1f}"  # noqa: E731
    lines = [f"# Research filters against the live book: {START} to {meta['end']}", "",
             f"**Membership basis: {meta['basis']}.** Membership file {meta['membership_file']} "
             f"(baseline {meta['baseline']}, {meta['changes']} changes); {meta['symbols']} symbols with "
             f"prices; {meta['ever_members_without_prices']} ever-members without prices. "
             f"{len(r)} sessions; halves split at {r.index[half]:%d %b %Y}.", "",
             "| Variant | A year | Max DD | Sharpe | Turnover % | Δ a year (90% range) | ahead in | "
             "Δ a year H1 / H2 | Δ max DD (90%) | Δ turnover (90%) | Verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        row = full.loc[n]
        if n == "live":
            lines.append(f"| **live** | {row['ann']:.1%} | {row['mdd']:.1%} | {row['sharpe']:.2f} | "
                         f"{row['turnover']:.0f} | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {n} | {row['ann']:.1%} | {row['mdd']:.1%} | {row['sharpe']:.2f} | {row['turnover']:.0f} | "
            f"{pct(row['d_ann'])} ({pct(row['d_ann_lo'])} to {pct(row['d_ann_hi'])}) | {row['p_better']:.0%} | "
            f"{pct(row['d_ann_h1'])} / {pct(row['d_ann_h2'])} | {pct(row['d_dd'])} "
            f"({pct(row['d_dd_lo'])} to {pct(row['d_dd_hi'])}) | {row['d_turn']:+.1f} "
            f"({row['d_turn_lo']:+.1f} to {row['d_turn_hi']:+.1f}) | {row['verdict']} |")
    lines += ["", f"## Walk-forward by family (each year from {FIRST_WF_YEAR}, best Sharpe on the years before)", "",
              "| Family | Δ a year vs live (90% range) | ahead in | Picks |", "|---|---|---|---|"]
    for fam, w in wf_rows.items():
        picks = ", ".join(f"{y}: {p}" for y, p in w["picks"].items())
        lines.append(f"| {fam} | {pct(w['d_ann'])} ({pct(w['lo'])} to {pct(w['hi'])}) | {w['p_better']:.0%} | {picks} |")
    if gate_off:
        lines += ["", "## Market gates: months whose signal was risk-off", ""]
        lines += [f"- {n}: {len(v)} ({', '.join(v) if v else 'none'})" for n, v in gate_off.items()]
    if exposure is not None:
        e = exposure.loc[exposure.index >= live_idx[0]]
        lines += ["", f"Volatility overlay: mean exposure {e.mean():.0%}, lowest {e.min():.0%} "
                      f"({e.idxmin():%b %Y})."]
    lines += ["", "Δ = variant minus live, same sessions. A year: compound annual net return. "
              "Bootstrap: paired, 63-session blocks (turnover: 3-month blocks), 2,000 draws.", ""]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    full.to_csv(out / "results.csv")
    (out / "walk_forward.json").write_text(json.dumps(wf_rows, indent=2))
    print("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--out", required=True)
    pr.add_argument("--workers", type=int, default=4)
    pr.add_argument("--membership", default=None, help="membership_history.json to use (default: the repo's)")
    pr.add_argument("--only", default="", help="comma-separated variants (live is always run)")
    rp = sub.add_parser("report")
    rp.add_argument("--out", required=True)
    args = p.parse_args()
    {"run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
