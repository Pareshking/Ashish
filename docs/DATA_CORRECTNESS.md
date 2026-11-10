# Data correctness

How the US data is sourced and checked, what was decided, and what is known
not to be checked. Update with every change to a source or a rule.

_Last updated: 2026-11-10_

## Sources

| Data | Source | Why | Cross-check |
|---|---|---|---|
| Daily OHLCV, split-adjusted | Yahoo via `yfinance` | Only free source with full history (1962+) for all 1,500 | Nasdaq.com historical API (official closes, 10 years) on a rotating sample; Polygon grouped-daily / Alpaca when keys exist |
| Dividends, splits | Yahoo via `yfinance` (`actions`) | Same calls as the prices | Price-jump audit: a one-day move beyond the threshold with no matching action is flagged |
| Membership, GICS sector and sub-industry | Wikipedia's S&P 500 / 400 / 600 lists (`scripts/sync_universe.py`) | S&P DJI publishes no free constituent file; yfinance has no membership endpoint | Row-count bounds per index; iShares / SPDR fund holdings (to do) |
| Benchmark | SPTM (SPDR Portfolio S&P 1500 Composite ETF), adjusted close | Yahoo's `^SP1500` has one row and no history (probed 10 Nov 2026) | `^GSPC`, `^SP400`, `^SP600` price indices |
| Trading calendar | `exchange_calendars` XNYS | NYSE publishes holidays and early closes years ahead | — |

## Findings from the 10 Nov 2026 probes (this session's network)

- Yahoo chart API: reachable. `yf.download` of 200 random members, full history,
  in 37 s; none empty. AAPL 9 Nov close 350.69 on Yahoo and on Nasdaq.com.
- Nasdaq.com historical API: reachable, 2,513 AAPL rows from 9 Nov 2016,
  split-adjusted official closes. One request per symbol.
- Stooq: connection reset from this session's proxy. Not usable here; not
  tested from GitHub Actions.
- Polygon, Alpaca: reachable, 401 without keys (owner to create free accounts).
- Wikipedia: S&P 500 503 rows, S&P 400 400, S&P 600 603 (1,502 symbols after
  removing names listed on two pages mid-move). The 400 and 600 pages carry a
  change log (626 and 491 rows); the 500 page no longer does.
- `^SP1500`: 1 row. `^SP1000`: rejects `period=max`. `^SP400`/`^MID` from 1981,
  `^SP600` from 1989, `^GSPC` from 1927.

## Backfill and audit, 10 Nov 2026

- Backfill from 2008-01-02 to 2026-11-09: 1,501 of 1,502 symbols, 6,043,329 rows,
  70 MB on disk (18 year files, 10 month files, 6 day files). **CWEN-A**
  (Clearway Energy class A): Yahoo returns no data under that ticker; not yet
  resolved.
- `scripts/audit_prices.py`, first run: 0 bounds faults; 402 one-day moves
  beyond 45% (24 in the last 400 sessions), reported not failed; 13 spikes, all
  before the last 400 sessions; 27 split-ratio moves, 25 old, 2 recent.
- The two recent ones, CORT 2025-12-31 (x0.496) and PRIM 2026-05-06 (x0.499),
  are real: Nasdaq.com shows -50.4% and -50.1% on the same sessions.
- Old split-day findings show Yahoo **does not adjust spin-offs**: EXPE
  2011-12-21 (TripAdvisor spin-off) has a 1-for-2 split and a $15.125
  "dividend" recorded, and the price still halves; SBRA 2010-11-16 likewise.
  IVT 2021-08-06 is junk from before the listing (zero volume). They cannot
  reach the 12-month ranking or the 6-month backtest; they would reach a long
  research backtest. Listed in the audit report, not corrected.
- Nasdaq.com API: a window whose end date is in the past returns no rows;
  windows must end today (handled in both scripts).

## Nasdaq cross-check, first run (10 Nov 2026): FAILED

150 random members, 336,125 (symbol, session) closes since Nov 2016:
**96.60% within 0.5%** of Nasdaq.com's official close; the pass mark is 99.5%.
3 symbols not served by Nasdaq. Worst agreement (closes within / compared):
HON 94/2512, FTV 344/2512, CBSH 988/2512, ADEA 1029/2512, O 1251/2512,
ZWS 1280/2512, HWM 1661/2512, TRN 2015/2512; SIRI worst 925% on 2024-09-10.

Lead, not yet evidence: these are companies with spin-offs, mergers or stock
dividends (Honeywell: Resideo/Garrett 2018, Solstice 2025; Fortive: Vontier
2020; Realty Income: Orion 2021; Howmet: Arconic 2020; Commerce Bancshares:
annual 5% stock dividends; Sirius XM: Liberty merger 2024). Nasdaq's series
appears adjusted for them and Yahoo's is not. **Open (B3): measure agreement
inside the last 400 sessions (what the ranking reads) and name each recent
event; decide a correction source before the site is linked.**

## Nasdaq cross-check, recent window (10 Nov 2026, iteration 2)

Same 150 symbols, last 400 sessions: 58,493 closes, **99.38% within 0.5%**
(bar 99.5%). Only two symbols disagree, and the earlier lead ("Yahoo does
not adjust spin-offs") is **wrong for both**:

- **HON**: Nasdaq.com's close goes 464.42 (2026-06-26) to 227.80
  (2026-06-29); Yahoo's is continuous (243.53 to 227.80) and records a split
  on 2026-06-29. Yahoo has adjusted the history for a separation, Nasdaq.com
  has not. For momentum the adjusted series is the right one (a holder kept
  the distributed shares). Event name not confirmed against a filing.
- **FTV**: Ralliant spin-off 2025-06-30; both adjust, factors 3.7% apart
  (Yahoo records a 1.327 split). Which is right is not checked.

Yahoo records recent spin-offs as fractional splits and adjusts by them; the
old unadjusted cases (EXPE 2011) predate that. Both are listed in
`data/nasdaq_exceptions.csv` with their evidence; the check reports their
earlier closes apart. Also: INTC's 2026-06-30 high 142.35 in
`data/all_time_highs.csv` equals Nasdaq.com's high for that session.

Rerun with the reviewed exceptions (same 150 symbols, 10 Nov 2026): **last 400
sessions 58,131 closes, 100.0000% within 0.5%** (HON's and FTV's closes before
their events left out and listed: 306 and 56 in the window). Whole ten years:
97.93% within 0.5% (the old spin-off and merger cases, SIRI, ADEA, CBSH, HWM,
O, ZWS..., reported, not failing). Not checked: the other ~1,350 symbols
(a sample rotates daily once the workflow runs).

## Decisions

- **Universe: S&P 1500, one system** (owner, 10 Nov 2026).
- **Storage in git, no object store** (owner). Closed years in
  `data/prices/YYYY.parquet`, closed months of the current year in
  `data/prices/YYYY-MM.parquet`, the current month as one small file per session
  in `data/prices/daily/`. A night's commit therefore adds ~50 KB, not the
  current year's ~7.5 MB (measured: 200 symbols, 2005-2026, zstd, ×7.5).
- **Split-adjusted closes are stored, dividend adjustment is computed** from the
  dividends table on load. Storing Yahoo's dividend-adjusted close would restate
  every year's file on every dividend. A split still restates the symbol's
  history; the sync rewrites that symbol's rows in every file it touches and
  logs it.

## Known limits (not hidden on the site)

- **Survivorship.** Free sources carry only today's members and drop delisted
  tickers. A backtest before point-in-time membership exists is run on today's
  list, which flatters momentum. Membership history accumulates from the first
  snapshot (10 Nov 2026); the 400/600 change logs can extend it back
  (to do), the 500's cannot from Wikipedia.
- **No exchange file.** The US has no free official all-stocks daily file like
  NSE's bhavcopy; closes are checked against Nasdaq.com on a sample, not all.
- **Sector is GICS as Wikipedia transcribes it**, not S&P's own file.
