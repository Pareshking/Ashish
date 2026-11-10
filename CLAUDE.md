# Working in this repository

This is the US Momentum Terminal: ranking, backtests and a track record on the
S&P 1500 (S&P 500 + MidCap 400 + SmallCap 600). It is a port of the NSE
Momentum Terminal (repository Pareshking/Paresh): same strategy, same website,
US data. The prices are the product, so **data correctness comes before
features**.

## Before any work on data

Read `docs/DATA_CORRECTNESS.md` (sources, decisions, known limits) and
`docs/TODO.md` (what is open, how we will know it is done).

## Rules that have been decided

- Judge a fix by independent evidence (a different source, dated, quoted). A
  check that reproduces our own numbers is a lead, not evidence. Say what was
  not checked.
- Do not change a price by hand. Fix the rule, or add a correction to
  `data/price_corrections.csv` with its evidence, then rerun the audits.
- Times are New York times (America/New_York) and sessions are NYSE sessions
  (`src/core/market_time.py`). GitHub Actions cron is UTC and ignores daylight
  saving, so every scheduled job runs twice and the script decides.
- Anything promised in a conversation goes in `docs/TODO.md` the same day.
- No India-specific feature is carried over from Paresh (owner, 10 Nov 2026).

## Working on a change

- Branch, commit and push to the branch you are given; pull requests are drafts.
- Tests: `python -m pytest tests -q`. Lint: `ruff check`. Files the nightly
  sync writes (`data/`) are not edited by hand.
- Update `CHANGELOG.md` for a user-visible change and `docs/TODO.md` for the
  state of the work.
