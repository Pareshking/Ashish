# Changelog

## Unreleased: second shadow and the tranching test

- A second forward shadow, residual momentum with volatility scaling (S1 + S2), recorded monthly beside the book (data/shadow_s1s2.json); not traded.
- Four weekly tranches for the live book tested (docs/MOMENTUM_PREREG.md); the live book is unchanged pending the owner's decision.

## Unreleased (PR #3): S&P 500 history and data fixes

- Research: nine published momentum improvements tested, pre-registered, on the point-in-time S&P 500 2011-2026 (docs/MOMENTUM_PREREG.md). One passed narrowly (S2, momentum-volatility scaling into SPY); it is recorded monthly as a shadow beside the book (data/shadow_s2.json), not traded.
- Track record re-struck after the data corrections: Jan-Oct 2026 +27.57% (was +30.77% at first strike).

- Prices for 153 former S&P 500 members Yahoo no longer serves, from the dataset Johnbrick123/sp500-data: 99% of 2010-2019 member-months now priced (85% before).

- Dividends adjust prices by the total-return convention (close + dividend over the previous close); a spin-off Yahoo records as both a split and a dividend is counted once. Corrects, for example, Danaher's Fortive day in July 2016 (+61% before, +3.6% now).
- S&P 500 month-end lists from Dec 2009 from an independent dataset (fja05680/sp500), which also corrects late Wikipedia lists at seven month-ends since 2019, including Dec 2025 (CRH, Carvana, Comfort Systems).

## Unreleased (PR #1): the US Momentum Terminal

- The main book is the S&P 500 (owner, 10 Nov 2026), measured against the S&P 500 with dividends; the S&P 400 and 600 remain selectable in Configuration and synced nightly.

- The strategy and website of the NSE Momentum Terminal (Pareshking/Paresh),
  ported to the S&P 1500 (S&P 500 + 400 + 600), one system.
- Prices from Yahoo Finance, committed to the repository (yearly, monthly and
  daily parquet files), checked nightly by an internal audit and weekly against
  Nasdaq.com's official closes. Membership and GICS sectors from Wikipedia's
  S&P lists; market caps from Nasdaq.com's screener.
- Track record from January 2026; January to October 2026 replayed on
  10 Nov 2026 on today's list, and marked so on the site.
- US settings (owner, 10 Nov 2026): $1M model book, trading cost 10 bps a round
  trip, risk-free rate 4.0%, benchmark the S&P 1500 (SPTM, total return), site
  name "Ashish Patel".
- Removed, as India-specific: FII/DII and NSDL flows, F&O list, results
  calendar, NSE sector indices, Kite upload and basket, CSV order export, the
  Indian financial-year column, rupee and crore formats.
- Research only (owner, 10 Nov 2026): additional momentum filters (frog in the
  pan, 52-week high, residual momentum gate, volatility, market trend and
  absolute momentum, seasonality, short-term reversal, MAX, Clenow's gap and
  trend quality, sector momentum) in `src/engine/filters.py`, wired into
  `run_backtest` as keywords that are off by default (results unchanged), and
  tested by `scripts/research_filters.py`; findings in
  `docs/RESEARCH_FILTERS.md`. No page, record or ranking uses them.
