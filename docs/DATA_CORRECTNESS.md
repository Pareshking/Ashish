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

## Momentum health and survivorship (10 Nov 2026)

`scripts/build_momentum_health.py --check-french`: this site's top-minus-bottom
fifth spread, scored each month-end since 2010 on TODAY's S&P 1500 list,
against Kenneth French's US momentum factor (UMD, Tuck data library, built on
CRSP with delisted stocks): 200 months, correlation 0.54 monthly (0.59 over 12
months), same sign 78%; mean -0.76 pts a month against UMD's +0.31. Paresh's
equivalent check (IIMA, point-in-time lists) was 0.83. The sign of the mean is
the survivorship bias, measured: the past losers in today's list are the ones
that came back. Decision: the Dashboard shows UMD, not our spread, until
point-in-time membership can carry it. The same bias is in the replayed record
months (Jan-Oct 2026, ten months, much less exposed than 16 years) and the
Backtest's History mode, and both say so.

## Point-in-time membership from Dec 2019 (10 Nov 2026, TODO B18)

`scripts/build_membership_history.py`: the S&P 500, 400 and 600 lists as Wikipedia showed them at each
month-end close since 31 Dec 2019 (the last revision saved by 16:00 New York that day; 1,268 / 590 / 720
revisions read, 83 month-ends each). Result: 83 change dates, 2,111 symbols ever, 1,475-1,506 members a
month-end (early months a little short: the 400 page then held 391-393 rows).

- **S&P 600, Dec 2019 - Feb 2021 (15 month-ends):** the page then held a stale S&P 1000 list (955-1,066
  rows, still carrying 18-22 S&P 500 names). Those month-ends are rebuilt instead by undoing the 600 page's
  dated change log from 31 Mar 2021. Checked on real snapshots: undoing the log from Dec 2022 to Mar 2021
  agrees on 592 of 601 names, Dec 2023 to Dec 2022 on 590, Dec 2025 to Dec 2024 on 586 of 602.
- **Ticker renames** (51) matched on the SEC CIK in Wikipedia's tables where present (Anthem->ELV,
  Alliance Data->BFH, FB->META, UTX->RTX...), else on the company name; a match where both tickers were
  listed at the same month-end is rejected. Rejected by hand with reasons: IBTX (not INDB), SIX (merged
  into Cedar Fair, FUN's earlier prices are Cedar Fair's).
- **Former members' prices** (`scripts/sync_former_members.py`, `data/former_members.csv`): of 609, 173
  priced from Yahoo, 51 renamed into today's members, 41 rejected as reused tickers (Yahoo's prices start
  after the membership spell), **344 with no data at Yahoo** (acquired or delisted: CXO, XLNX, ATVI, MDC,
  WRK, ...); Nasdaq.com serves none of the five tried. Member-months with prices: 79.1% (Jan 2020) rising
  to 91.2% (Jan 2024), mean 88.9%. Unpriced members are left out of each month's scoring.
- **The bias, measured again** (top-minus-bottom fifth by our score against Kenneth French's UMD, Feb 2020
  - Sep 2026, 80 months): today's list -1.02%/month (corr 0.56) -> point-in-time **+0.26%/month against
  UMD's +0.24 (corr 0.77)**. Most of the survivorship bias is gone; the 11% unpriced remains a lead to close
  (Tiingo's free tier serves delisted US tickers, 500 a month: needs the owner's key; Stooq from GitHub
  Actions, untested).
- **Second source for delisted members** (owner's suggestion, 10 Nov 2026: public GitHub datasets).
  `scripts/import_former_members_github.py` reads **Stonks/tickers** (per-ticker CSVs by exchange) through
  raw.githubusercontent.com. What it is, checked on 30 current members against our Yahoo store: Yahoo's
  ADJUSTED prices as of a 10 Oct 2023 snapshot (non-dividend payers equal ours exactly: META, LSCC, PENN,
  IPGP, ACAD, ANIP, LRN, VCYT; dividend payers sit below by their dividend factor: IBM 0.81, GS 0.90). So
  the closes are total-return closes, stored as Close with no dividend rows, and every file stops on
  2023-10-10. Of the 385 former members Yahoo lacks: 156 covered for their whole spell, 159 to Oct 2023 only
  (delisted later), 7 rejected (the file starts after the spell: another company), 63 in neither source.
  Member-months priced: mean **97.0%** (Jan 2020 95.8%, lowest 90.5% at Oct 2023 when the snapshot ends).
  Spread re-checked: +0.27%/month against UMD's +0.24 (corr 0.77, 1,442 stocks scored a month). Audit of the
  imported rows since mid-2019: spikes on BBBY (Jan/Feb 2023 meme rallies, real) and four energy names on
  2020-03-13 (plausible); RCM 2022-11-08 x0.502 with no split recorded, **unexplained, not verified** (no
  second source serves delisted names). About a third of the files carry no volume (stored as 0; volume
  feeds only the optional liquidity floor). Other GitHub datasets tried (teddykoker/survivorship-free-spy,
  koa-fin/dva, hackingthemarkets/*, jcwill415/*) end in 2018-2022 or hold returns, not prices.
- Not checked: the month-end lists against Wayback Machine snapshots (CDX unreachable from this session);
  the CIK renames individually.

## S&P 500 from Dec 2009; independent cross-checks (10 Nov 2026, TODO B24-B28)

**Membership.** The month-end lists now come from github:fja05680/sp500
(`scripts/import_sp500_history.py`): Andreas Clenow's list from *Trading
Evolved* to 2019, then maintained from S&P's announcements. Against our
Wikipedia revisions for Dec 2019 - Aug 2026 the two agree on 99.97% of
member-months; the 7 month-ends that differ are in
`reports/sp500_source_check.csv`. Where checked, S&P Dow Jones's own releases
side with the dataset: Etsy, Teradyne and Catalent joined before the open on
21 Sep 2020 (press.spglobal.com, 4 Sep 2020) and CRH, Carvana and Comfort
Systems on 22 Dec 2025 (press.spglobal.com, 5 Dec 2025), but the Wikipedia
revisions at those month-ends still listed the stocks they replaced. A hand-edited
page lags; a month-end snapshot inherits the lag. The 2020 June change (BIO,
TDY, TYL) and Nov 2025 (SNDK for IPG) were not checked against a release.
After the dataset's last date (18 Aug 2026) our Wikipedia/nightly snapshots
carry on. The S&P 400 and 600 timelines are still Wikipedia's and probably
lag the same way (not measured).

**Prices, checked against github:Johnbrick123/sp500-data** (prices for every
S&P 500 member since 1996; it states each member-day 1970-2024 was compared
with CRSP's daily total return). Its claims were tested here, not taken:
- Cash takeovers end at the offer, within cents: Whole Foods 41.99 (offer 42),
  Monsanto 127.95 (128), Tiffany 131.46 (131.50), Sigma-Aldrich 139.76 (140),
  Pall 127.11 (127.20), XL 57.59 (57.60). The offer prices are from memory,
  not re-read from filings.
- Over each 2010-2019 S&P 500 former member's spell, 643 of 649 symbols agree
  with our Yahoo/Stonks prices (daily-return correlation ≥0.95). The 5 that do
  not are OUR error: CPWR, EP, KG, GENZ, LSI are another company's prices under
  a reused ticker whose new owner's history starts before the old spell, which
  our start-date test cannot see (B26).
- Over 1,604,302 S&P 500 member-days 2010-2024, 126 differ by more than 0.5
  pt after the dividend fix below (136 before).

**Dividend adjustment changed** (B27): the ex-date return is now
(close + dividend) / previous close, the CRSP and S&P convention, not Yahoo's
factor 1 - D / previous close, which overstates a large special (KDP's $103.75
on 10 Jul 2018: +1.8% for the holder, +11.5% by Yahoo's factor). A dividend of
2% or more beside a split ratio no board would declare is a spin-off Yahoo has
written twice and is applied once (DHR 5 Jul 2016: split 1.319 and dividend
24.56 for Fortive; +61% before, +3.6% now, the close's own move).

Not checked: the dataset's licence (none is published; it contains Tiingo,
Quandl WIKI and CRSP rows), so nothing from it is committed until the owner
decides (B25).

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
