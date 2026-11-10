"""S&P 500 book with stacked filters (owner, 10 Nov 2026: "S&P 500 with more
filters"). Combinations FIXED BEFORE ANY RESULT, from the sources' recipes:

  C1  Gray & Vogel: drop the worse half of the qualified by FIP
  C2  C1 + no new buys while the S&P 500 is below its 10-month SMA (Faber)
  C3  C2 + the stock's GICS sector in the stronger half by 12-month return
         + the stock's own 12-month return above the 4% risk-free rate

Each against the S&P 500 book with no extra filter, Jan 2020 - last completed
month, point-in-time S&P 500 members (data/membership_monthly.csv), the live
record's configuration otherwise. Reported: a year, max drawdown, Sharpe,
both halves, and a paired 63-session block bootstrap (2,000 draws).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from scripts.research_filters import live_kwargs, RISK_FREE  # noqa: E402
from src.engine import filters, membership as mem  # noqa: E402
from src.engine.backtester import run_backtest  # noqa: E402
from src.engine.model_record import record_sector_map  # noqa: E402
from src.loaders import benchmark_store as bs, nse_long  # noqa: E402


def sp500_history() -> dict:
    pm = pd.read_csv(os.path.join(ROOT, "data", "membership_monthly.csv"), parse_dates=["Date"])
    al = json.load(open(os.path.join(ROOT, "data", "membership_history.json")))["aliases"]
    h = mem.empty_history("S&P 500")
    for d, g in pm[pm["Index"] == "S&P 500"].groupby("Date"):
        h, _ = mem.record_snapshot(h, d.date(), g["Yahoo"])
    h["aliases"] = al
    return h


def run(name, close, h, bench, extra):
    months = (pd.Period(pd.Timestamp.today(), freq="M") - pd.Period("2020-01", freq="M")).n
    r = run_backtest(f"combo_{name}", close, **live_kwargs(), sector_map=record_sector_map(close.columns),
                     _benchmark_close=bench, backtest_months=months, _membership=h, stateful_history=True,
                     history_start=pd.Timestamp("2020-01-01"), research_label=(f"combo_{name}" if extra else None), **extra)
    eq = pd.Series(r["equity_curve"]).dropna()
    return eq.pct_change().dropna()


def stats(d: pd.Series) -> dict:
    eq = (1 + d).cumprod()
    yrs = len(d) / 252
    a = eq.iloc[-1] ** (1 / yrs) - 1
    ex = d - RISK_FREE / 252
    return {"a_year": a * 100, "max_dd": (eq / eq.cummax() - 1).min() * 100,
            "sharpe": ex.mean() / d.std() * np.sqrt(252)}


def main() -> int:
    close = nse_long.load()[0].loc["2018-06-01":].astype("float64")
    h = sp500_history()
    ever = set(h["baseline"]["symbols"]).union(*[set(c["added"]) for c in h["changes"]])
    ever |= {h["aliases"][s]["new_symbol"] for s in ever if s in h["aliases"]}
    close = close[[c for c in close.columns if c in ever]]
    bench = bs.history("max", "SPTM_TR")
    spx = bs.history("max", "^GSPC")
    fip = -filters.frog_in_the_pan(close, 252, 21)
    market = filters.faber_trend(spx, 10, close.index)
    sector = filters.industry_momentum(close, record_sector_map(close.columns)).attrs["rank"] > 0.5
    own = filters.period_return(close, 252) > RISK_FREE
    mkt_frame = pd.DataFrame(np.repeat(market.reindex(close.index).fillna(True).to_numpy()[:, None], close.shape[1], 1),
                             index=close.index, columns=close.columns)
    combos = {
        "base": {},
        "C1": dict(_research_values=fip, research_drop=0.5, research_gate_on="buy"),
        "C2": dict(_research_values=fip, research_drop=0.5, _research_gate=market, research_gate_on="buy"),
        "C3": dict(_research_values=fip, research_drop=0.5,
                   _research_gate=(mkt_frame & sector.reindex_like(close).fillna(False) & own.fillna(False)),
                   research_gate_on="buy"),
    }
    rets = {k: run(k, close, h, bench, v) for k, v in combos.items()}
    df = pd.DataFrame(rets).dropna()
    b = bench.reindex(df.index).pct_change().fillna(0)
    rows = []
    rng = np.random.default_rng(0)
    n, blk = len(df), 63
    for k in df:
        s = stats(df[k])
        h1, h2 = df.iloc[: n // 2], df.iloc[n // 2:]
        d1 = stats(h1[k])["a_year"] - stats(h1["base"])["a_year"]
        d2 = stats(h2[k])["a_year"] - stats(h2["base"])["a_year"]
        draws = []
        for _ in range(2000 if k != "base" else 0):
            idx = np.concatenate([np.arange(st, min(st + blk, n)) for st in rng.integers(0, n - blk, n // blk + 1)])[:n]
            draws.append(stats(df[k].iloc[idx])["a_year"] - stats(df["base"].iloc[idx])["a_year"])
        lo, hi = (np.percentile(draws, [5, 95]) if draws else (np.nan, np.nan))
        rows.append((k, s["a_year"], s["max_dd"], s["sharpe"], s["a_year"] - stats(df["base"])["a_year"], d1, d2, lo, hi,
                     np.mean(np.array(draws) > 0) * 100 if draws else np.nan))
    out = pd.DataFrame(rows, columns=["variant", "a_year", "max_dd", "sharpe", "vs_base", "H1", "H2", "p5", "p95", "ahead_pct"])
    sb = stats(b)
    print(f"{df.index[0].date()}..{df.index[-1].date()}, point-in-time S&P 500; S&P 1500 TR {sb['a_year']:.1f}% a year, "
          f"max DD {sb['max_dd']:.1f}%")
    print(out.round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
