# To do

The one list of what is open. Tick an item when it is done and verified, with
the date and the evidence; add anything promised in a conversation the same day.

_Last updated: 2026-11-10_

## Build (owner, 10 Nov 2026): port Paresh to the S&P 1500

Owner decisions, 10 Nov: S&P 500 + 400 + 600, one system; strategy rules as
Paresh; same website minus every India-specific feature (FII/DII, NSDL FPI,
F&O list, results calendar, Kite or CSV order export, NSE sector indices);
model book $1M; sector from the best free source (GICS via Wikipedia), else
Yahoo; yfinance unless shown unreliable; no R2; schedules in New York time;
test everything before the Streamlit site is linked. Work runs in half-hourly
iterations from 16:01 IST.

| # | What | How we know it is done | Status |
|---|---|---|---|
| B1 | Probe sources; universe with GICS; storage plan | Findings in DATA_CORRECTNESS; `data/universe.csv` with 1,500±10 rows | [x] 10 Nov: 1,502 symbols; sizes measured |
| B2 | Price store and nightly sync (yfinance, NYSE calendar, yearly/monthly/daily files) | Backfill committed; a rerun of the same night changes nothing; audit of jumps vs actions passes or lists each exception | [ ] |
| B3 | Cross-check against Nasdaq.com official closes | Sample of ≥100 symbols × 10 years: share of closes within 0.5%, every exception named | [ ] 10 Nov first run FAILED: 96.6% within 0.5% (bar 99.5%); worst are spin-off/merger names (HON, FTV, O, HWM, JNJ, SIRI). Next: agreement inside the last 400 sessions, each recent event named, correction source decided. 10 Nov it.2: last 400 sessions 99.38%, only HON and FTV, both Yahoo-adjusted spin-offs Nasdaq.com treats differently (reviewed in `data/nasdaq_exceptions.csv`); rerun 100.00% of 58,131 closes. Left: the daily rotating sample in a workflow |
| B4 | Engine and core ported, India modules removed | `pytest` green on the ported engine tests | [ ] 10 Nov it.2: every module imports; app wired to US loaders; Dashboard renders headless, 0 exceptions, cold 9.7 s, peak <600 MB (was 1,045). Left: port Paresh's engine tests; ₹/Cr → $ pass (86 sites); FII/DII, Kite, NSE text on the other pages |
| B5 | Website ported (11 pages less India features), $1M book | Every page and a stock page render in headless Chromium with no exception; screenshots | [ ] |
| B6 | Workflows in New York time | Each runs green once by hand; double-cron guard tested for EST and EDT | [ ] |
| B7 | Membership history before 10 Nov 2026 from the 400/600 change logs | Rebuilt list on a dated past day matches an independent snapshot (fund holdings or archive) | [ ] |
| B8 | Owner: free Polygon and Alpaca keys as repo secrets | Secrets present; nightly cross-check runs | [ ] owner |
| B9 | Owner links Streamlit Cloud | Site loads on the owner's phone | [ ] after B1-B6 |
| B11 | Owner decisions: US market facts. Transaction cost kept at Paresh's 30 bps a side (US costs are lower, a few bps on the S&P 1500); risk-free 4.0% (3-month T-bill, was India's 6.5%) | Owner confirms or names values | [ ] owner |
| B12 | Members on the Wikipedia list with no Yahoo price for 5+ sessions (10 Nov: ACA, BLFS, HLX, LEG, QRVO, RAMP; CWEN-A never) are not ranked and the audit fails on them | Each confirmed as acquired/delisted from a dated source, or its price restored | [ ] |
| B13 | Owner decision: the site's name (header, tab, footer). Paresh's shows its owner's name; set to "US Momentum Terminal" for now (`SITE_NAME`) | Owner names it | [ ] owner |
| B14 | Localisation: ₹ and Indian digit grouping (Portfolio "₹9,36,523"), Cr units, Kite on Actions, NSE/Nifty/Zerodha in Guide, Sectors and Breadth captions, Paresh's Indian figures in the momentum-health captions | QA script finds none of: Nifty NSE ₹ crore lakh Kite Zerodha FII DII IST Cr, on every page | [ ] |
| B15 | Portfolio: "Since inception −6.3%" equals MTD while the S&P 1500 reads +11.3% since inception | Both rows measured from the same start, matching an independent recomputation | [ ] |
| B10 | Owner decision: track-record inception. Paresh's record starts Jan 2026 (replayed months). Here a month before Dec 2026 can only be replayed on today's list (survivorship). Proposal: live record from December 2026 (signal 30 Nov, the first after the build); Backtest page shows the last 6 completed months as Paresh's does | Owner says which month | [ ] owner |

## Iteration log

- **Iteration 1 (10 Nov, from 16:01 IST):** probes; universe (1,502); `market_time` on XNYS; price store (`src/loaders/price_store.py`), nightly/backfill sync, Nasdaq cross-check and internal price audit scripts; engine, core and website copied from Paresh with the India-only engine modules removed (sector indices, results calendar, source check, reconcile, parity audit); `systems.py` reduced to one system; `corporate_actions.py` reduced to a confirmed-events hook. Backfill from 2008 running.
- **Iteration 2 (10 Nov, from 16:31 IST):** US loaders (price source, benchmarks, market caps from Nasdaq's screener, all-time highs from Yahoo's full history, index levels, NYSE holidays, former members, ranking store without R2); `config.py` for the US ($1M book; cost and risk-free flagged B11); app.py wired; Configuration without the system picker or NSE sync; Dashboard without NSE board meetings, sector indices or FII/DII flows; size leadership on the S&P 500/400/600; stale members not ranked (B12); memory of a cold start cut from 1,045 to <600 MB (per-file pivots; full history only for Backtest). Nasdaq cross-check over the last 400 sessions: 99.38% (HON, FTV only; both reviewed as adjustment differences in `data/nasdaq_exceptions.csv`, rerun pending). INTC's 2026-06-30 high 142.35 equals Nasdaq.com's.
