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
| B3 | Cross-check against Nasdaq.com official closes | Sample of ≥100 symbols × 10 years: share of closes within 0.5%, every exception named | [ ] 10 Nov first run FAILED: 96.6% within 0.5% (bar 99.5%); worst are spin-off/merger names (HON, FTV, O, HWM, JNJ, SIRI). Next: agreement inside the last 400 sessions, each recent event named, correction source decided |
| B4 | Engine and core ported, India modules removed | `pytest` green on the ported engine tests | [ ] |
| B5 | Website ported (11 pages less India features), $1M book | Every page and a stock page render in headless Chromium with no exception; screenshots | [ ] |
| B6 | Workflows in New York time | Each runs green once by hand; double-cron guard tested for EST and EDT | [ ] |
| B7 | Membership history before 10 Nov 2026 from the 400/600 change logs | Rebuilt list on a dated past day matches an independent snapshot (fund holdings or archive) | [ ] |
| B8 | Owner: free Polygon and Alpaca keys as repo secrets | Secrets present; nightly cross-check runs | [ ] owner |
| B9 | Owner links Streamlit Cloud | Site loads on the owner's phone | [ ] after B1-B6 |
| B10 | Owner decision: track-record inception. Paresh's record starts Jan 2026 (replayed months). Here a month before Dec 2026 can only be replayed on today's list (survivorship). Proposal: live record from December 2026 (signal 30 Nov, the first after the build); Backtest page shows the last 6 completed months as Paresh's does | Owner says which month | [ ] owner |

## Iteration log

- **Iteration 1 (10 Nov, from 16:01 IST):** probes; universe (1,502); `market_time` on XNYS; price store (`src/loaders/price_store.py`), nightly/backfill sync, Nasdaq cross-check and internal price audit scripts; engine, core and website copied from Paresh with the India-only engine modules removed (sector indices, results calendar, source check, reconcile, parity audit); `systems.py` reduced to one system; `corporate_actions.py` reduced to a confirmed-events hook. Backfill from 2008 running.
