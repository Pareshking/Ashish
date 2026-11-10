# Changelog

## Unreleased (PR #1): the US Momentum Terminal

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
