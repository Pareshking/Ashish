#!/usr/bin/env python3
"""Stage 3 of the pre-registered study: the framework itself
(docs/MOMENTUM_PREREG.md, "Stage 3: the framework itself").

    python scripts/research_prereg_stage3.py run --out DIR --reuse STAGE1_DIR [--workers 3]
    python scripts/research_prereg_stage3.py report --out DIR

F1 raw momentum (score_method "return"), F2 the same names weighted by 63-session
mean traded value (stock cap 15%, sector 40%), F3 fifty names (buffer 100), each
against the stage-1 base at four offsets and 10/20 bps, judged by section 3.3 on
the CAGR gap. Beside each: CAGR against SPY_TR and against the equal-weight
point-in-time S&P 500 (members at each month end, their next month's total
return from price_store.adjusted_close), and the share of months ahead of each.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import research_prereg as R  # noqa: E402

# STAGE_VARIANTS picks the variants (stage 4: "L,F2d,F2"); default stage 3's.
import os  # noqa: E402

VARIANTS = tuple(v for v in os.environ.get("STAGE_VARIANTS", "F1,F2,F3").split(",") if v)
TEXT = {"F1": "Raw momentum (score_method 'return')",
        "F2": "Traded-value weights (63 sessions), stock cap 15%, sector 40%",
        "F3": "Fifty names, buffer 100",
        "L": "The live rules from the start: winners run to 15%, buys 5%, resets Mar/Sep",
        "F2d": "F2's traded-value targets under the live rules (drift; resets Mar/Sep)",
        "IV": "Inverse-volatility weights (63 sessions), stock cap 5%",
        "IVd": "Inverse-volatility targets under the live rules"}
for _v in VARIANTS:
    R.KIND[_v] = "selection"


def cmd_run(args) -> None:
    out, reuse = Path(args.out), Path(args.reuse)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    shutil.copy(reuse / "meta.json", out / "meta.json")
    for c in R.COSTS:
        for o in R.OFFSETS:
            for suf in (".json", ".parquet", ".monthly.parquet"):
                f = f"{R.run_label('base', o, c)}{suf}"
                if not (out / "runs" / f).exists():
                    shutil.copy(reuse / "runs" / f, out / "runs" / f)
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
    print(f"reuse check: identical={same}", flush=True)
    if not same:
        raise SystemExit("The base differs from a fresh run: the data changed; rerun the base too.")
    todo = [(n, o, c) for c in R.COSTS for n in VARIANTS for o in R.OFFSETS
            if not (out / "runs" / f"{R.run_label(n, o, c)}.json").exists()]
    print(f"{len(todo)} runs, {args.workers} workers", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(args.workers, initializer=R._init_worker, initargs=(None,)) as pool:
        futs = {pool.submit(R._run_one, n, o, c, str(out)): (n, o, c) for n, o, c in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            n, o, c = futs[fut]
            try:
                lab, secs = fut.result()
                print(f"[{i}/{len(todo)}] {lab} in {secs:.0f}s ({(time.perf_counter() - t0) / 60:.1f} min)", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{i}/{len(todo)}] {R.run_label(n, o, c)} FAILED: {type(exc).__name__}: {exc}", flush=True)


# ── benchmarks ───────────────────────────────────────────────────────────────

def ew_sp500_monthly() -> pd.Series:
    """Equal-weight point-in-time S&P 500: for month k, the mean over the members
    at the end of month k-1 of their month-k total return (adjusted closes; a
    member with no close at either month end is left out)."""
    from src.engine.membership import members_on

    inp = R.load_inputs(None)
    close = inp["close"]
    rows = R.month_last_rows(close.index)
    mc = close.ffill(limit=5).iloc[rows.to_numpy()]
    mc.index = rows.index
    ret = mc / mc.shift(1) - 1.0
    out = {}
    for k in ret.index[1:]:
        d = close.index[int(rows[k - 1])]
        mem = members_on(inp["membership"], d.date(), canonical=True)
        if mem is None:
            continue
        cols = ret.columns[ret.columns.isin(list(mem))]
        r = ret.loc[k, cols].dropna()
        out[k] = {"ret": float(r.mean()), "n": int(len(r)), "members": len(mem)}
    return pd.DataFrame(out).T


def monthly(daily: pd.Series) -> pd.Series:
    return (1.0 + daily).groupby(daily.index.to_period("M")).prod() - 1.0


def m_stats(r: pd.Series, rf_m: pd.Series) -> dict:
    r = r.dropna()
    n = len(r)
    cagr = float(np.prod(1 + r) ** (12 / n) - 1)
    eq = np.cumprod(1 + r.to_numpy())
    mdd = float((eq / np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:] - 1).min())
    x = r - rf_m.reindex(r.index).fillna(rf_m.iloc[-1])
    return {"cagr": cagr, "mdd": mdd, "sharpe": float(x.mean() / x.std(ddof=1) * math.sqrt(12)), "months": n}


def cmd_report(args) -> None:
    out = Path(args.out)
    meta = json.loads((out / "meta.json").read_text())
    s2 = meta["section2"]
    d0, end = pd.Timestamp(s2["common_first_fill_d0"]), pd.Timestamp(s2["end_date"])
    rets, mons = R._load_runs(out)
    fr = R.load_french()
    rf_d, rf_m = fr["ff3_d"]["RF"], fr["ff3_m"]["RF"]
    from src.loaders import benchmark_store

    spy = pd.to_numeric(benchmark_store.history("max", "SPY_TR"), errors="coerce").dropna()
    spy_r = spy.pct_change(fill_method=None)
    ew = ew_sp500_monthly()
    names = ["base", *VARIANTS]
    turn = {(n, o, c): pd.Series(mons[R.run_label(n, o, c)]["Turnover %"].to_numpy(float),
                                 index=pd.to_datetime(mons[R.run_label(n, o, c)]["Period Start"]))
            for n in names for o in R.OFFSETS for c in R.COSTS}
    results, bench = {}, {}
    for sname, start in (("primary", d0), ("secondary", pd.Timestamp("2019-12-31"))):
        results[sname] = {}
        for c in R.COSTS:
            keys = [(n, o) for n in names for o in R.OFFSETS]
            X = pd.concat([rets[R.run_label(n, o, c)] for n, o in keys], axis=1, keys=range(len(keys)), sort=True)
            X = X[(X.index > start) & (X.index <= end)]
            assert not X.isna().any().any()
            rf = rf_d.reindex(X.index).ffill().fillna(rf_d.iloc[-1]).to_numpy()
            A = X.to_numpy()
            T = len(A)
            years = T / R.TRADING_DAYS
            col = {k: i for i, k in enumerate(keys)}
            met = R._metrics(A, rf)
            half = T // 2
            mh = [R._metrics(A[:half], rf[:half]), R._metrics(A[half:], rf[half:])]
            rng = np.random.default_rng(R.SEED)
            boot = {m: np.empty((R.N_DRAWS, A.shape[1])) for m in ("cagr", "sharpe", "mdd")}
            for i in range(R.N_DRAWS):
                ix = R.block_indices(T, R.BLOCK, rng)
                mi = R._metrics(A[ix], rf[ix])
                for m in boot:
                    boot[m][i] = mi[m]
            spy_s = spy_r.reindex(X.index).fillna(0.0)
            ew_s = ew["ret"]
            months = [p for p in ew_s.index if start.to_period("M") <= p <= end.to_period("M")]
            if start.day > 25:                               # 2020+: from January 2020
                months = [p for p in months if p > start.to_period("M")]
            rows = {}
            for n in names:
                ii = [col[(n, o)] for o in R.OFFSETS]
                mo = [monthly(X.iloc[:, col[(n, o)]]).reindex(months) for o in R.OFFSETS]
                spy_m = monthly(spy_s).reindex(months)
                tov = [float(turn[(n, o, c)][(turn[(n, o, c)].index >= start) & (turn[(n, o, c)].index < end)].sum()
                             / years) for o in R.OFFSETS]
                row = {"cagr": float(np.mean(met["cagr"][ii])), "mdd": float(np.mean(met["mdd"][ii])),
                       "sharpe": float(np.mean(met["sharpe"][ii])), "turnover": float(np.mean(tov)),
                       "by_offset": {o: {"cagr": float(met["cagr"][col[(n, o)]]), "mdd": float(met["mdd"][col[(n, o)]]),
                                         "sharpe": float(met["sharpe"][col[(n, o)]])} for o in R.OFFSETS},
                       "ahead_spy_months": float(np.mean([(m > spy_m).mean() for m in mo])),
                       "ahead_ew_months": float(np.mean([(m > ew_s.reindex(months)).mean() for m in mo]))}
                if n != "base":
                    g = {}
                    for m in ("cagr", "sharpe", "mdd"):
                        def gap(arr, n=n, m=m):
                            return np.mean([arr[..., col[(n, o)]] - arr[..., col[("base", o)]] for o in R.OFFSETS], axis=0)
                        g[m] = float(gap(met[m]))
                        g[f"{m}_h1"], g[f"{m}_h2"] = float(gap(mh[0][m])), float(gap(mh[1][m]))
                        b = gap(boot[m])
                        g[f"{m}_lo"], g[f"{m}_hi"] = float(np.percentile(b, 5)), float(np.percentile(b, 95))
                        g[f"{m}_p"] = float((b > 0).mean())
                        g[f"{m}_by_offset"] = {o: float(met[m][col[(n, o)]] - met[m][col[("base", o)]]) for o in R.OFFSETS}
                    g["turnover"] = float(np.mean(tov) - rows["base"]["turnover"])
                    row["vs_base"] = g
                rows[n] = row
            results[sname][c] = {"rows": rows, "first": str(X.index[0].date()), "last": str(X.index[-1].date()),
                                 "sessions": T, "half_split": str(X.index[half].date())}
            if c == 10.0:
                spy_d = spy_s.to_numpy()[:, None]
                ms = R._metrics(spy_d, rf)
                bench[sname] = {"SPY_TR": {"cagr": float(ms["cagr"][0]), "mdd": float(ms["mdd"][0]),
                                           "sharpe": float(ms["sharpe"][0]), "basis": "daily"},
                                "EW S&P 500 (PIT)": {**m_stats(ew_s.reindex(months), rf_m), "basis": "monthly"},
                                "months": f"{months[0]} to {months[-1]}", "n_months": len(months),
                                "ew_mean_members_priced": float(ew.loc[months, "n"].mean()),
                                "ew_mean_members": float(ew.loc[months, "members"].mean())}
    verdicts = {s: {n: R.verdict(n, results[s][10.0], results[s][20.0]) for n in VARIANTS} for s in results}

    pct = lambda v: f"{v * 100:+.2f}"  # noqa: E731
    L = []
    for sname in results:
        st, st20, bm = results[sname][10.0], results[sname][20.0], bench[sname]
        L += [f"#### {sname.title()} sample ({st['first']} to {st['last']}, {st['sessions']} sessions, halves split "
              f"{st['half_split']}; benchmark months {bm['months']})", "",
              "| Book | CAGR | Max DD | Sharpe | Turn./yr | CAGR vs SPY_TR | CAGR vs EW S&P 500 | Months ahead of SPY_TR "
              "| Months ahead of EW | CAGR gap vs base (90% range) | Ahead in | H1 / H2 | By offset 0/5/10/15 | Gap at 20 bps "
              "| ΔMDD | ΔTurn. | Verdict |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for n in ["base", *VARIANTS]:
            r = st["rows"][n]
            head = (f"| {n if n == 'base' else n + ': ' + TEXT[n]} | {r['cagr']:.2%} | {r['mdd']:.1%} | {r['sharpe']:.2f} | "
                    f"{r['turnover']:.0f} | {pct(r['cagr'] - bm['SPY_TR']['cagr'])} | "
                    f"{pct(r['cagr'] - bm['EW S&P 500 (PIT)']['cagr'])} | {r['ahead_spy_months']:.0%} | "
                    f"{r['ahead_ew_months']:.0%} |")
            if n == "base":
                L.append(head + " — | — | — | " + " / ".join(f"{v['cagr']:.1%}" for v in r["by_offset"].values())
                         + " (CAGR) | — | — | — | — |")
                continue
            g, g20 = r["vs_base"], st20["rows"][n]["vs_base"]
            L.append(head + f" {pct(g['cagr'])} ({pct(g['cagr_lo'])} to {pct(g['cagr_hi'])}) | {g['cagr_p']:.1%} | "
                     f"{pct(g['cagr_h1'])} / {pct(g['cagr_h2'])} | "
                     + " / ".join(pct(v) for v in g["cagr_by_offset"].values())
                     + f" | {pct(g20['cagr'])} | {pct(g['mdd'])} | {g['turnover']:+.0f} | **{verdicts[sname][n][0]}** |")
        L += ["", f"Benchmarks: SPY_TR {bm['SPY_TR']['cagr']:.2%} / {bm['SPY_TR']['mdd']:.1%} / {bm['SPY_TR']['sharpe']:.2f} "
              f"(CAGR / max DD / Sharpe, daily); equal-weight point-in-time S&P 500 "
              f"{bm['EW S&P 500 (PIT)']['cagr']:.2%} / {bm['EW S&P 500 (PIT)']['mdd']:.1%} / "
              f"{bm['EW S&P 500 (PIT)']['sharpe']:.2f} (monthly; {bm['ew_mean_members_priced']:.0f} of "
              f"{bm['ew_mean_members']:.0f} members priced a month on average). Sharpe of SPY_TR on French daily RF, of "
              f"the EW index on French monthly RF.", "",
              "Verdict reasons: " + "; ".join(f"{n} {v[0]}" + (f" ({', '.join(v[1])})" if v[1] else "")
                                              for n, v in verdicts[sname].items()) + ".", ""]
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "results.json").write_text(json.dumps({"results": {s: {str(int(c)): v for c, v in d.items()}
                                                              for s, d in results.items()},
                                                  "bench": bench, "verdicts": verdicts}, indent=1, default=str))
    print("\n".join(L))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--out", required=True)
    pr.add_argument("--reuse", required=True)
    pr.add_argument("--workers", type=int, default=3)
    rp = sub.add_parser("report")
    rp.add_argument("--out", required=True)
    args = p.parse_args()
    {"run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
