#!/usr/bin/env python3
"""Stage 2 of the pre-registered study: combinations (docs/MOMENTUM_PREREG.md,
"Stage 2: combinations (pre-registered 10 Nov 2026)").

    python scripts/research_prereg_stage2.py run --out DIR --reuse STAGE1_DIR [--workers 3]
    python scripts/research_prereg_stage2.py report --out DIR

48 combinations: 8 selection sets (S1, S4, S7 each on or off) x overlay (none,
S2, S3) x tranching (off, on). Components are stage 1's, unchanged
(scripts/research_prereg.py). The base, S1, S4 and S7 runs are reused from a
stage-1 directory on the same data; the four new selection sets are run here.
One combination is chosen on 2011-2019 (highest CAGR with max drawdown no more
than 2 pts worse than the base's) and judged once on 2020-2026, with a
deflated Sharpe ratio over all 48.
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import math
import shutil
import sys
import time
from statistics import NormalDist
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import research_prereg as R  # noqa: E402

SELECTION = ("S1", "S4", "S7")
OVERLAYS = ("none", "S2", "S3")
IS_END = pd.Timestamp("2019-12-31")
OOS_START = pd.Timestamp("2020-01-01")
EULER = 0.5772156649


def selection_sets() -> list[str]:
    out = []
    for k in range(len(SELECTION) + 1):
        for c in itertools.combinations(SELECTION, k):
            out.append("+".join(c) if c else "base")
    return out


def combos() -> list[tuple[str, str, bool]]:
    return [(s, o, t) for s in selection_sets() for o in OVERLAYS for t in (False, True)]


def combo_name(s: str, o: str, t: bool) -> str:
    parts = [] if s == "base" else s.split("+")
    if o != "none":
        parts.append(o)
    if t:
        parts.append("S5")
    return "+".join(parts) if parts else "base"


def n_components(s: str, o: str, t: bool) -> int:
    return (0 if s == "base" else len(s.split("+"))) + (o != "none") + int(t)


# ── run ──────────────────────────────────────────────────────────────────────

def cmd_run(args) -> None:
    out, reuse = Path(args.out), Path(args.reuse)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    shutil.copy(reuse / "meta.json", out / "meta.json")
    copied = 0
    for s in ("base", *SELECTION):
        for c in R.COSTS:
            for o in R.OFFSETS:
                lab = R.run_label(s, o, c)
                for suf in (".json", ".parquet", ".monthly.parquet"):
                    src = reuse / "runs" / f"{lab}{suf}"
                    if not (out / "runs" / f"{lab}{suf}").exists():
                        shutil.copy(src, out / "runs" / f"{lab}{suf}")
                        copied += 1
    print(f"reused {copied} files from {reuse}", flush=True)
    # Reuse check: one stage-1 run recomputed now must equal the stored one to the bit.
    chk = out / "reuse_check"
    (chk / "runs").mkdir(parents=True, exist_ok=True)
    logging.disable(logging.WARNING)
    if not (chk / "runs" / "base_o0_c10.parquet").exists():
        R._init_worker(None)
        R._run_one("base", 0, 10.0, str(chk))
    a = pd.read_parquet(chk / "runs" / "base_o0_c10.parquet")["net"]
    b = pd.read_parquet(reuse / "runs" / "base_o0_c10.parquet")["net"]
    same = a.index.equals(b.index) and a.to_numpy().tobytes() == b.to_numpy().tobytes()
    (out / "reuse_check.json").write_text(json.dumps({"base_o0_c10_identical": bool(same)}))
    print(f"reuse check (base_o0_c10 recomputed vs stage 1): identical={same}", flush=True)
    if not same:
        raise SystemExit("Stage-1 runs differ from a fresh run: the data changed; rerun everything.")
    new_sets = [s for s in selection_sets() if s.count("+") >= 1]
    todo = [(s, o, c) for c in R.COSTS for s in new_sets for o in R.OFFSETS
            if not (out / "runs" / f"{R.run_label(s, o, c)}.json").exists()]
    print(f"{len(todo)} new runs, {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers, initializer=R._init_worker, initargs=(None,)) as pool:
        futs = {pool.submit(R._run_one, s, o, c, str(out)): (s, o, c) for s, o, c in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            s, o, c = futs[fut]
            try:
                lab, secs = fut.result()
                print(f"[{i}/{len(todo)}] {lab} in {secs:.0f}s ({(time.perf_counter() - t0) / 60:.1f} min)",
                      flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{i}/{len(todo)}] {R.run_label(s, o, c)} FAILED: {type(exc).__name__}: {exc}", flush=True)


# ── statistics ───────────────────────────────────────────────────────────────

def build(out: Path, meta: dict):
    from src.loaders import benchmark_store

    rets, mons = R._load_runs(out)
    fr = R.load_french()
    dm = R.dm_inputs(fr)
    par = meta["S3"]
    spy = pd.to_numeric(benchmark_store.history("max", "SPY_TR"), errors="coerce").dropna()
    spy_r = spy.reindex(spy.index).pct_change(fill_method=None)
    cal = spy.index
    wcache: dict = {}

    def weight(kind):
        def f(m):
            if (kind, m) not in wcache:
                wcache[(kind, m)] = R.s2_weight(fr["umd_d"], m - 1) if kind == "S2" else R.s3_weight(dm, par, m)
            return wcache[(kind, m)]
        return f

    d0 = pd.Timestamp(meta["section2"]["common_first_fill_d0"])
    series = {}
    for c in R.COSTS:
        for s in selection_sets():
            for ov in OVERLAYS:
                per = {}
                for o in R.OFFSETS:
                    lab = R.run_label(s, o, c)
                    if ov == "none":
                        per[o] = rets[lab]
                    else:
                        per[o] = R.overlay(rets[lab], mons[lab], spy_r, weight(ov), c, cal)[0]
                series[(s, ov, False, c)] = per
                eq = pd.concat([(1.0 + per[o][per[o].index > d0]).cumprod() for o in R.OFFSETS], axis=1).dropna()
                tot = eq.mean(axis=1)
                tr = tot.pct_change()
                tr.iloc[0] = tot.iloc[0] - 1.0
                series[(s, ov, True, c)] = {o: tr for o in R.OFFSETS}
    return series, fr["ff3_d"]["RF"]


def _period_matrix(series, keys, cost, start, end):
    cols, idx = [], []
    for k in keys:
        for o in R.OFFSETS:
            cols.append(series[(*k, cost)][o])
            idx.append((k, o))
    X = pd.concat(cols, axis=1, keys=range(len(cols)))
    X = X[(X.index > start) & (X.index <= end)]
    if X.isna().any().any():
        raise RuntimeError("gaps in a combination's series")
    return X, idx


def period_stats(series, keys, rf_all, cost, start, end):
    X, idx = _period_matrix(series, keys, cost, start, end)
    rf = rf_all.reindex(X.index).ffill().fillna(rf_all.iloc[-1]).to_numpy()
    A = X.to_numpy()
    m = R._metrics(A, rf)
    ex = A - rf[:, None]
    dev = ex - ex.mean(axis=0)
    sd = np.sqrt((dev ** 2).mean(axis=0))
    sk = (dev ** 3).mean(axis=0) / sd ** 3          # population moments
    ku = (dev ** 4).mean(axis=0) / sd ** 4          # non-excess kurtosis
    col = {k: i for i, k in enumerate(idx)}
    out = {}
    for k in keys:
        ii = [col[(k, o)] for o in R.OFFSETS]
        out[k] = {"cagr": float(np.mean(m["cagr"][ii])), "mdd": float(np.mean(m["mdd"][ii])),
                  "sharpe": float(np.mean(m["sharpe"][ii])), "skew": float(np.mean(sk[ii])),
                  "kurt": float(np.mean(ku[ii])),
                  "by_offset": {o: {"cagr": float(m["cagr"][col[(k, o)]]), "sharpe": float(m["sharpe"][col[(k, o)]]),
                                    "mdd": float(m["mdd"][col[(k, o)]])} for o in R.OFFSETS}}
    return out, X, rf, col


def deflated_sharpe(sr_ann: float, srs_ann: list[float], T: int, skew: float, kurt: float) -> dict:
    n = len(srs_ann)
    sr = sr_ann / math.sqrt(R.TRADING_DAYS)
    v = float(np.var(np.asarray(srs_ann) / math.sqrt(R.TRADING_DAYS), ddof=1))
    z = NormalDist().inv_cdf
    sr0 = math.sqrt(v) * ((1 - EULER) * z(1 - 1 / n) + EULER * z(1 - 1 / (n * math.e)))
    den = math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr * sr)
    dsr = float(NormalDist().cdf((sr - sr0) * math.sqrt(T - 1) / den))
    return {"N": n, "sr_daily": sr, "var_sr_daily": v, "sr0_daily": sr0, "sr0_annual": sr0 * math.sqrt(252),
            "T": T, "skew": skew, "kurt": kurt, "dsr": dsr}


def cmd_report(args) -> None:
    out = Path(args.out)
    meta = json.loads((out / "meta.json").read_text())
    s2 = meta["section2"]
    d0, end = pd.Timestamp(s2["common_first_fill_d0"]), pd.Timestamp(s2["end_date"])
    series, rf_all = build(out, meta)
    keys = combos()
    base = ("base", "none", False)
    res = {}
    for c in R.COSTS:
        res[("is", c)] = period_stats(series, keys, rf_all, c, d0, IS_END)
        res[("oos", c)] = period_stats(series, keys, rf_all, c, IS_END, end)
    st_is = res[("is", 10.0)][0]
    st_oos = res[("oos", 10.0)][0]
    limit = st_is[base]["mdd"] - 0.02
    eligible = [k for k in keys if st_is[k]["mdd"] >= limit]
    chosen = sorted(eligible, key=lambda k: (-round(st_is[k]["cagr"], 12), n_components(*k)))[0]
    T_is = len(res[("is", 10.0)][1])
    dsr = deflated_sharpe(st_is[chosen]["sharpe"], [st_is[k]["sharpe"] for k in keys], T_is,
                          st_is[chosen]["skew"], st_is[chosen]["kurt"])

    # Out-of-sample judgement of the chosen combination.
    _, X, rf, col = res[("oos", 10.0)]
    A = X.to_numpy()
    T = len(A)
    rng = np.random.default_rng(R.SEED)
    ci = [col[(chosen, o)] for o in R.OFFSETS]
    bi = [col[(base, o)] for o in R.OFFSETS]
    d_cagr, d_sh = np.empty(R.N_DRAWS), np.empty(R.N_DRAWS)
    sub = A[:, ci + bi]
    for i in range(R.N_DRAWS):
        ix = R.block_indices(T, R.BLOCK, rng)
        m = R._metrics(sub[ix], rf[ix])
        d_cagr[i] = m["cagr"][:4].mean() - m["cagr"][4:].mean()
        d_sh[i] = m["sharpe"][:4].mean() - m["sharpe"][4:].mean()
    oc, ob = st_oos[chosen], st_oos[base]
    oc20, ob20 = res[("oos", 20.0)][0][chosen], res[("oos", 20.0)][0][base]
    checks = {
        "1_cagr_and_sharpe_gap_positive": bool(oc["cagr"] > ob["cagr"] and oc["sharpe"] > ob["sharpe"]),
        "2_bootstrap_cagr_ahead_ge_90pct": bool((d_cagr > 0).mean() >= 0.90),
        "3_ahead_at_all_four_offsets": bool(all(oc["by_offset"][o]["cagr"] > ob["by_offset"][o]["cagr"]
                                                for o in R.OFFSETS)),
        "4_ahead_at_20bps": bool(oc20["cagr"] > ob20["cagr"]),
        "5_mdd_no_more_than_2pts_worse": bool(oc["mdd"] - ob["mdd"] >= -0.02),
        "6_dsr_ge_0.95": bool(dsr["dsr"] >= 0.95),
    }
    if chosen == base:
        verdict = "none chosen (the base had the highest in-sample CAGR)"
    elif all(checks.values()):
        verdict = "pass"
    elif oc["cagr"] < ob["cagr"]:
        verdict = "reject"
    else:
        verdict = "inconclusive"
    oos_rank = sorted(keys, key=lambda k: -st_oos[k]["cagr"])
    rank = oos_rank.index(chosen) + 1

    pct = lambda v: f"{v * 100:+.2f}"  # noqa: E731
    name = lambda k: combo_name(*k)  # noqa: E731
    L = [f"Chosen in sample: **{name(chosen)}** ({n_components(*chosen)} components). "
         f"In-sample sessions {T_is} (to {IS_END.date()}); out-of-sample {T} (2 Jan 2020 to {end.date()}). "
         f"Base in-sample max drawdown {st_is[base]['mdd']:.2%}, so the limit was {limit:.2%}; "
         f"{len(eligible)} of {len(keys)} combinations eligible.", "",
         "| | In sample: CAGR / MDD / Sharpe | Out of sample: CAGR / MDD / Sharpe | OOS at 20 bps CAGR |",
         "|---|---|---|---|"]
    for lab, k in (("Base", base), (f"Chosen: {name(chosen)}", chosen)):
        a, b = st_is[k], st_oos[k]
        L.append(f"| {lab} | {a['cagr']:.2%} / {a['mdd']:.1%} / {a['sharpe']:.3f} | "
                 f"{b['cagr']:.2%} / {b['mdd']:.1%} / {b['sharpe']:.3f} | {res[('oos', 20.0)][0][k]['cagr']:.2%} |")
    L += ["", f"Out of sample, chosen minus base: CAGR {pct(oc['cagr'] - ob['cagr'])} pt (90% range "
          f"{pct(np.percentile(d_cagr, 5))} to {pct(np.percentile(d_cagr, 95))}; ahead in {(d_cagr > 0).mean():.1%} "
          f"of draws), Sharpe {oc['sharpe'] - ob['sharpe']:+.3f} (ahead in {(d_sh > 0).mean():.1%}), max drawdown "
          f"{pct(oc['mdd'] - ob['mdd'])} pt; by offset 0/5/10/15 CAGR "
          + " / ".join(pct(oc["by_offset"][o]["cagr"] - ob["by_offset"][o]["cagr"]) for o in R.OFFSETS)
          + f"; at 20 bps {pct(oc20['cagr'] - ob20['cagr'])} pt.", "",
          f"Deflated Sharpe ratio: in-sample Sharpe {st_is[chosen]['sharpe']:.3f} a year "
          f"({dsr['sr_daily']:.4f} a day), N = {dsr['N']}, variance of the {dsr['N']} in-sample daily Sharpe ratios "
          f"{dsr['var_sr_daily']:.3e}, expected maximum SR* = {dsr['sr0_daily']:.4f} a day ({dsr['sr0_annual']:.3f} a year), "
          f"T = {dsr['T']}, skew {dsr['skew']:.3f}, kurtosis {dsr['kurt']:.2f}: **DSR = {dsr['dsr']:.3f}**.", "",
          "Checks: " + "; ".join(f"{k.split('_', 1)[0]} {'yes' if v else 'NO'}" for k, v in checks.items())
          + f". **Verdict: {verdict}.** Out-of-sample CAGR rank of the chosen combination: {rank} of {len(keys)}.", "",
          "| # | Combination | Components | IS CAGR | IS MDD | IS Sharpe | Eligible | OOS CAGR | OOS MDD | OOS Sharpe "
          "| OOS rank | OOS CAGR at 20 bps |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, k in enumerate(keys, 1):
        a, b = st_is[k], st_oos[k]
        L.append(f"| {i} | {'**' + name(k) + '**' if k == chosen else name(k)} | {n_components(*k)} | {a['cagr']:.2%} | "
                 f"{a['mdd']:.1%} | {a['sharpe']:.3f} | {'yes' if k in eligible else 'no'} | {b['cagr']:.2%} | "
                 f"{b['mdd']:.1%} | {b['sharpe']:.3f} | {oos_rank.index(k) + 1} | "
                 f"{res[('oos', 20.0)][0][k]['cagr']:.2%} |")
    L += ["", "Hindsight, not a verdict: the five highest out-of-sample CAGRs were "
          + "; ".join(f"{name(k)} {st_oos[k]['cagr']:.2%} (in sample {st_is[k]['cagr']:.2%}, "
                      f"{'eligible' if k in eligible else 'not eligible'})" for k in oos_rank[:5]) + "."]
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "results.json").write_text(json.dumps({
        "chosen": name(chosen), "verdict": verdict, "checks": checks, "dsr": dsr, "oos_rank": rank,
        "bootstrap": {"cagr_p": float((d_cagr > 0).mean()), "sharpe_p": float((d_sh > 0).mean())},
        "is": {name(k): {kk: v for kk, v in st_is[k].items() if kk != "by_offset"} for k in keys},
        "oos": {name(k): {kk: v for kk, v in st_oos[k].items() if kk != "by_offset"} for k in keys},
        "top5_oos": [name(k) for k in oos_rank[:5]], "eligible": [name(k) for k in eligible]}, indent=1))
    print("\n".join(L))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--out", required=True)
    pr.add_argument("--reuse", required=True, help="the stage-1 run directory on the same data")
    pr.add_argument("--workers", type=int, default=3)
    rp = sub.add_parser("report")
    rp.add_argument("--out", required=True)
    args = p.parse_args()
    {"run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
