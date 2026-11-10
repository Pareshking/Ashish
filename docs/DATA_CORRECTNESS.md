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
