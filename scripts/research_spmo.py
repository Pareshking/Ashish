#!/usr/bin/env python3
"""Stage 6: the S&P 500 Momentum index's method on the point-in-time S&P 500
(docs/MOMENTUM_PREREG.md, "Stage 6"), checked against the real ETF (SPMO) and
judged against L (the live book under the owner's rules), F2 and SPY.

    python scripts/research_spmo.py --out DIR --runs STAGE4_DIR

STAGE4_DIR holds the stage-4 runs (L and F2 at four offsets, 10 and 20 bps).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import research_prereg as R  # noqa: E402

N, TOP_IN, KEEP, CAP, CAP_MULT, LOOK, SKIP = 100, 80, 120, 0.09, 3.0, 252, 21


def third_friday(year: int, month: int) -> pd.Timestamp:
    d = pd.Timestamp(year=year, month=month, day=1)
    first_fri = d + pd.Timedelta(days=(4 - d.weekday()) % 7)
    return first_fri + pd.Timedelta(days=14)


def cap_weights(raw: pd.Series, limit: pd.Series) -> pd.Series:
    """Normalise `raw`, cap each name at `limit`, spread the excess pro rata."""
    w = raw / raw.sum()
    for _ in range(100):
        over = w > limit + 1e-12
        if not over.any():
            break
        excess = float((w[over] - limit[over]).sum())
        w[over] = limit[over]
        free = ~over & (w < limit - 1e-12)
        if not free.any():
            break
        w[free] += excess * w[free] / w[free].sum()
    return w / w.sum()


def schedule(idx: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    out = []
    for y in range(idx[0].year, idx[-1].year + 1):
        for ref_m, eff_m in ((2, 3), (8, 9)):
            ref = idx[idx <= pd.Timestamp(year=y, month=ref_m, day=1) + pd.offsets.MonthEnd(0)]
            eff = idx[idx <= third_friday(y, eff_m)]
            if len(ref) and len(eff) and ref[-1].month == ref_m and eff[-1] > ref[-1]:
                out.append((ref[-1], eff[-1]))
    return out


def book_weights(close, size, membership, ref, prev: set[str]) -> tuple[pd.Series, set[str]]:
    from src.engine.membership import members_on
    i = close.index.get_loc(ref)
    if i < LOOK:
        return pd.Series(dtype=float), prev
    mem = [s for s in (members_on(membership, ref.date(), canonical=True) or []) if s in close.columns]
    win = close[mem].iloc[i - LOOK: i + 1]
    ok = win.notna().sum() >= LOOK * 0.9
    win = win.loc[:, ok]
    p_end, p_start = win.iloc[-1 - SKIP], win.iloc[0]
    vol = win.pct_change(fill_method=None).std()
    mv = (p_end / p_start - 1) / vol
    mv = mv.replace([np.inf, -np.inf], np.nan).dropna()
    z = ((mv - mv.mean()) / mv.std()).clip(-3, 3)
    rank = z.rank(ascending=False)
    chosen = list(rank[rank <= TOP_IN].index)
    chosen += [s for s in rank[(rank > TOP_IN) & (rank <= KEEP)].sort_values().index if s in prev]
    for s in rank.sort_values().index:
        if len(chosen) >= N:
            break
        if s not in chosen:
            chosen.append(s)
    chosen = chosen[:N]
    sz = size.loc[ref].reindex(z.index)
    sz = sz.fillna(sz.median())
    universe_w = sz / sz.sum()
    f = z[chosen].map(lambda v: 1 + v if v > 0 else 1 / (1 - v))
    raw = sz[chosen] * f
    limit = np.minimum(CAP, CAP_MULT * universe_w[chosen])
    return cap_weights(raw, limit), set(chosen)


def simulate(inp: dict, cost_bps: float) -> tuple[pd.Series, pd.DataFrame]:
    close = inp["close"]
    size = R.traded_value(inp["split_close"], inp["volume"])
    rets = close.pct_change(fill_method=None).fillna(0.0)
    sched = schedule(close.index)
    daily = pd.Series(0.0, index=close.index)
    log = []
    w = pd.Series(dtype=float)
    prev: set[str] = set()
    for j, (ref, eff) in enumerate(sched):
        target, prev_new = book_weights(close, size, inp["membership"], ref, prev)
        if target.empty:
            continue
        end = sched[j + 1][1] if j + 1 < len(sched) else close.index[-1]
        allnames = target.index.union(w.index)
        turn = float((target.reindex(allnames).fillna(0) - w.reindex(allnames).fillna(0)).abs().sum())
        cost = turn * cost_bps / 2 / 1e4
        seg = close.index[(close.index > eff) & (close.index <= end)]
        cur = target.copy()
        for k, d in enumerate(seg):
            r = rets.loc[d, cur.index]
            day = float((cur * r).sum())
            if k == 0:
                day -= cost
            daily.loc[d] = day
            cur = cur * (1 + r)
            cur = cur / cur.sum()
        log.append({"ref": str(ref.date()), "effective": str(eff.date()), "names": len(target),
                    "max_w": float(target.max()), "turnover": turn,
                    "top": ", ".join(f"{s} {v:.1%}" for s, v in target.sort_values(ascending=False).head(5).items())})
        w, prev = cur, prev_new
    first = pd.Timestamp(log[0]["effective"]) if log else close.index[0]
    return daily[daily.index > first], pd.DataFrame(log)


def spmo_check(rep: pd.Series) -> dict:
    import yfinance as yf
    px = yf.download("SPMO", start="2015-10-01", auto_adjust=True, progress=False)["Close"]
    px = (px.iloc[:, 0] if isinstance(px, pd.DataFrame) else px).dropna()
    a = (1 + rep).groupby(rep.index.to_period("M")).prod() - 1
    b = px.resample("ME").last().pct_change().dropna()
    b.index = b.index.to_period("M")
    m = pd.concat([a, b], axis=1, keys=["rep", "spmo"]).dropna().iloc[1:]
    def cagr(x):
        return float((1 + x).prod() ** (12 / len(x)) - 1)
    return {"months": len(m), "first": str(m.index[0]), "last": str(m.index[-1]),
            "corr": float(m.corr().iloc[0, 1]), "cagr_rep": cagr(m["rep"]), "cagr_spmo": cagr(m["spmo"]),
            "te": float((m["rep"] - m["spmo"]).std() * np.sqrt(12)),
            "mean_diff_a_year": float((m["rep"] - m["spmo"]).mean() * 12)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.WARNING)
    inp = R.load_inputs(None)
    reps = {}
    for c in R.COSTS:
        reps[c], log = simulate(inp, c)
        reps[c].rename("net").to_frame().to_parquet(out / f"spmo_c{int(c)}.parquet")
        if c == 10.0:
            log.to_csv(out / "rebalances.csv", index=False)
    check = spmo_check(reps[10.0])
    (out / "spmo_check.json").write_text(json.dumps(check, indent=1))
    print("replication vs SPMO:", json.dumps(check))

    rets, _ = R._load_runs(Path(args.runs))
    fr = R.load_french()
    rf_d = fr["ff3_d"]["RF"]
    from src.loaders import benchmark_store
    spy = pd.to_numeric(benchmark_store.history("max", "SPY_TR"), errors="coerce").dropna().pct_change(fill_method=None)
    meta = json.loads((Path(args.runs) / "meta.json").read_text())
    d0, end = pd.Timestamp(meta["section2"]["common_first_fill_d0"]), pd.Timestamp(meta["section2"]["end_date"])
    res = {}
    for sname, start in (("primary", d0), ("secondary", pd.Timestamp("2019-12-31"))):
        res[sname] = {}
        for c in R.COSTS:
            cols = {"SPMO-R": reps[c]}
            for n in ("L", "F2"):
                for o in R.OFFSETS:
                    cols[f"{n}_o{o}"] = rets[R.run_label(n, o, c)]
            cols["SPY"] = spy
            X = pd.concat(cols, axis=1, sort=True)
            X = X[(X.index > start) & (X.index <= end)].dropna()
            A, rf = X.to_numpy(), rf_d.reindex(X.index).ffill().fillna(rf_d.iloc[-1]).to_numpy()
            k = {n: i for i, n in enumerate(X.columns)}
            met = R._metrics(A, rf)
            T, half = len(A), len(A) // 2
            mh = [R._metrics(A[:half], rf[:half]), R._metrics(A[half:], rf[half:])]
            rng = np.random.default_rng(R.SEED)
            boot = np.empty((R.N_DRAWS, A.shape[1]))
            for i in range(R.N_DRAWS):
                boot[i] = R._metrics(A[R.block_indices(T, R.BLOCK, rng)], rf)["cagr"]

            def mean_of(arr, n):
                return np.mean([arr[..., k[f"{n}_o{o}"]] for o in R.OFFSETS], axis=0)

            row = {}
            for n in ("SPMO-R", "L", "F2", "SPY"):
                pick = (lambda a, n=n: a[..., k[n]]) if n in ("SPMO-R", "SPY") else (lambda a, n=n: mean_of(a, n))
                row[n] = {m: float(pick(met[m])) for m in ("cagr", "mdd", "sharpe")}
            gaps = {}
            for vs in ("L", "F2", "SPY"):
                ref = (lambda a, vs=vs: a[..., k[vs]]) if vs == "SPY" else (lambda a, vs=vs: mean_of(a, vs))
                b = boot[:, k["SPMO-R"]] - ref(boot)
                gaps[vs] = {"cagr": float(met["cagr"][k["SPMO-R"]] - ref(met["cagr"])),
                            "h1": float(mh[0]["cagr"][k["SPMO-R"]] - ref(mh[0]["cagr"])),
                            "h2": float(mh[1]["cagr"][k["SPMO-R"]] - ref(mh[1]["cagr"])),
                            "p": float((b > R.EPS).mean()), "lo": float(np.percentile(b, 5)),
                            "hi": float(np.percentile(b, 95)),
                            "mdd": float(met["mdd"][k["SPMO-R"]] - ref(met["mdd"]))}
            res[sname][int(c)] = {"rows": row, "gaps": gaps, "first": str(X.index[0].date()),
                                  "last": str(X.index[-1].date())}
    (out / "results.json").write_text(json.dumps({"check": check, "results": res}, indent=1))
    for sname, d in res.items():
        r, g = d[10]["rows"], d[10]["gaps"]
        print(f"== {sname} {d[10]['first']} to {d[10]['last']} (10 bps)")
        for n, v in r.items():
            print(f"  {n:7s} CAGR {v['cagr']:.2%}  MDD {v['mdd']:.1%}  Sharpe {v['sharpe']:.2f}")
        for vs, v in g.items():
            print(f"  SPMO-R vs {vs}: {v['cagr'] * 100:+.2f} pts ({v['lo'] * 100:+.2f} to {v['hi'] * 100:+.2f}); "
                  f"halves {v['h1'] * 100:+.2f}/{v['h2'] * 100:+.2f}; ahead in {v['p']:.1%}; dMDD {v['mdd'] * 100:+.1f}; "
                  f"at 20 bps {d[20]['gaps'][vs]['cagr'] * 100:+.2f}")


if __name__ == "__main__":
    main()
