# Additional momentum filters: literature and tests (10 Nov 2026)

**Answer, on today's S&P 1500 list (survivorship-biased): none of the filters
tested is reliably better than the live book.** 23 variants of 12 families were
tested; 13 are worse in both halves or in at least 80% of bootstrap draws
(rejected), 8 are inconclusive, and one passed the rules set in advance: a
**sector-momentum buy gate** (buy only names whose GICS sector is in the
stronger half by 12-month return). It passed narrowly. The same gate on 6-month
sector returns failed, and 1 pass in 23 tries is about what luck gives. It is
the only one worth recording forward as a shadow, and only after a rerun on
point-in-time membership. Nothing here is recommended for the live record; that
is the owner's decision.

Owner, 10 Nov 2026: "We need other additional filters like FIP (frog in the
pan), and others you need to find from books related to momentum and
momentum-related research papers, trend following research papers ...
satisfying my portfolio construction requirements, my strategy. Basically
aligning with my framework."

Code: `src/engine/filters.py` (the measures), `run_backtest`'s research keywords
(`src/engine/backtester.py`, off by default), `scripts/research_filters.py`
(the test). Tests: `tests/test_research_filters.py`,
`tests/test_research_filters_plumbing.py`.

## The framework every filter must fit

Read from the code, not changed:

- **Universe:** the S&P 1500, one system. Yahoo daily closes, split-adjusted,
  dividend-adjusted on load (`src/loaders/price_source.py`).
- **Score:** System-1 Sharpe momentum (`src/engine/calendar_momentum.py`):
  calendar-month horizons of 1, 3, 6, 9 and 12 months, each window's
  risk-adjusted return, winsorised z-scores, blended 10/30/30/20/10. No skip
  month, no R-squared.
- **Book** (`track_record.TRACK_RECORD_CONFIG`): the top 20 of the names that
  pass the filters, 5% each, kept while ranked in the top 40. Filters: close
  above the 50-day EMA and within 20% of the 52-week high. Caps: 5% a stock
  and 40% a GICS sector, hard at rebalance. Monthly: signal at the month's last
  session, fill at the next close. From the 30 Nov 2026 signal a six-monthly
  reset (March and September), hold cap 15%, new buys 5%. Cost 10 bps a round
  trip.
- **Removed systems stay removed.** The original terminal deleted its
  alternative RANKINGS, residual alpha and exponential regression among them
  (Paresh `tests/test_removed_systems_stay_removed.py`). Nothing here ranks.
  Each filter is one of these:
  - a **buy gate**: a name not held must pass it to be bought;
  - a **keep gate**: a holding must pass it to stay;
  - a **tie-break**: among the top 40 qualified names, new buys are taken in
    the filter's order instead of the score's (Gray & Vogel's second sort);
  - a **market gate**: the whole market is risk-off, so there are no new buys
    or the book goes to cash.

## How the filters plug in

`run_backtest` has six new keywords, all off by default:

| Keyword | What it does |
|---|---|
| `_research_gate` | Booleans, True = may hold. A frame (sessions × symbols) is a stock gate; a series is a market gate (False fails every name). Read at the signal row. |
| `_research_values` + `research_drop` | Of the names that pass every other rule, the worst `research_drop` share by these values (higher = better) fail. A relative gate, as Gray & Vogel drop the worse half. |
| `research_gate_on` | Who the gate and the drop apply to: `"buy"` (names not held), `"keep"` (holdings) or `"both"`. |
| `_research_values` + `research_pool` | The first `research_pool` ranked names are reordered by the values; the buffer still keeps any holding in the top 40. |
| `research_label` | Required with any of them: the Streamlit cache key does not see the underscored frames. |

The pending rebalance that Actions and Portfolio show applies the same rules,
so a research run's "current book" is the book the rule would hold.

**Defaults are byte-identical.** `tests/test_research_filters_plumbing.py`
proves this in two ways:

1. A synthetic run with the record's rules (caps, buffer, hold cap, six-monthly
   reset) hashes to the value the engine gave before these keywords existed
   (commit 715782d).
2. A gate that passes everyone, a 0% drop and a one-name pool exercise every
   new line, and must reproduce the default run to the bit.

Checked once on the real store before the commit: the engine at 715782d and
this one, live configuration, January 2020 to October 2026. The equity curve,
all 2,439 tradebook rows, the live book, the month changes and the stats were
identical. `TRACK_RECORD_CONFIG`, `src/core/config.py`, `data/` and every
page's defaults are unchanged.

## How the filters were tested

`python scripts/research_filters.py run --out DIR` and then `report --out DIR`.
24 runs at about 10 s each, 1 minute on 4 workers.

- **Sample:** January 2020 to October 2026 (82 months, 1,694 sessions). The
  owner wants no backtest before 2020. The live run gives 18.9% a year, max
  drawdown −36.9% and Sharpe 0.63. A direct `run_backtest` call with
  TRACK_RECORD_CONFIG gives the same figures.
- **Membership basis: TODAY'S LIST.** `data/membership_history.json` has its
  baseline at 10 Nov 2026 and no changes. The rebuild from Wikipedia revisions
  was not finished when this ran: `/home/user/Ashish`'s copy was checked and
  also had its baseline at 2026-11-10. So every month is scored on today's
  1,501 members, which is survivorship-biased. On that list the score's
  top-minus-bottom spread averaged −0.76 pts a month, against +0.31 for French's
  UMD (DATA_CORRECTNESS). Survivors flatter every variant alike, but not
  equally: a filter that favours names which later stayed in the index looks
  better than it is. One ever-member has no prices (CWEN-A).
- **Thresholds were fixed before any run** and not tuned: the source's own
  value where it gives one (Clenow's 15% and 90 days, Faber's 10 months, Daniel
  & Moskowitz's 24 months, Gray & Vogel's half), otherwise one round value
  (20%, top 40).
- **Controls:**
  1. **Halves:** the gap in a year's return in each half of the sessions
     (split 16 May 2023).
  2. **Bootstrap:** a paired block bootstrap, 63-session blocks, 2,000 draws,
     for a year's return and max drawdown; turnover on 3-month blocks. Each
     gives a 90% range and the share of draws in which the variant is ahead.
  3. **Walk-forward by family:** each year from 2022, keep whichever of
     {live, the family's variants} had the best Sharpe on all earlier sessions
     from 2020, then chain those years.
- **Verdict rules, fixed in advance:**
  - **shadow:** both halves ahead on a year's return; ahead in at least 80% of
    draws; max drawdown no more than 2 pts worse; and the family's
    walk-forward not behind live.
  - **reject:** both halves behind, or ahead in at most 20% of draws.
  - **inconclusive:** anything else.

  With 23 variants, one or two "shadow" results are expected from luck alone.
  A year of return differences over 82 months has a standard error of about
  ±3 pts.

## Results (today's list, survivorship-biased; Jan 2020 – Oct 2026)

Δ is the variant minus the live book on the same sessions.

| Variant | A year | Max DD | Sharpe | Turnover % | Δ a year (90% range) | Ahead in | Δ H1 / H2 | Δ max DD (90%) | Δ turnover (90%) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **live** | 18.9% | −36.9% | 0.63 | 50 | — | — | — | — | — | — |
| fip_pool40 | 19.1% | −35.7% | 0.64 | 57 | +0.2 (−5.8 to +4.8) | 40% | +3.9 / −4.1 | +1.2 (−2.8 to +6.0) | +7.1 (+5.4 to +9.2) | inconclusive |
| fip_drop50 | 18.1% | −40.3% | 0.60 | 47 | −0.8 (−6.2 to +4.3) | 38% | +2.5 / −4.6 | −3.5 (−6.1 to +3.8) | −3.3 (−4.6 to −1.9) | inconclusive |
| fip_drop20 | 19.3% | −38.0% | 0.65 | 48 | +0.4 (−3.1 to +4.1) | 57% | +1.9 / −1.4 | −1.1 (−2.8 to +3.0) | −1.4 (−2.3 to −0.5) | inconclusive |
| fip_drop20_both | 18.5% | −38.2% | 0.63 | 49 | −0.3 (−3.9 to +3.6) | 43% | +1.4 / −2.4 | −1.3 (−3.2 to +3.0) | −1.1 (−2.0 to −0.1) | inconclusive |
| high90 | 16.4% | −35.1% | 0.57 | 52 | −2.5 (−7.2 to +0.9) | 11% | −3.0 / −1.8 | +1.8 (−3.1 to +2.9) | +2.5 (+1.3 to +3.9) | reject |
| gh_pool40 | 17.8% | −32.4% | 0.63 | 54 | −1.1 (−6.3 to +1.8) | 20% | +0.1 / −2.5 | +4.4 (−0.5 to +6.9) | +3.7 (+2.5 to +5.1) | reject |
| resid_drop50 | 16.6% | −38.5% | 0.57 | 48 | −2.3 (−6.4 to +2.0) | 20% | +0.1 / −5.0 | −1.6 (−4.2 to +3.5) | −1.6 (−2.8 to −0.4) | inconclusive |
| resid_pos | 18.3% | −39.3% | 0.62 | 48 | −0.6 (−4.2 to +3.4) | 42% | +1.0 / −2.3 | −2.4 (−4.0 to +3.3) | −1.4 (−2.4 to −0.4) | inconclusive |
| vol_target | 13.5% | −34.3% | 0.50 | 46 | −5.4 (−13.8 to −0.4) | 3% | −8.6 / −1.4 | +2.6 (−0.7 to +7.2) | −4.1 (−5.9 to −1.5) | reject |
| vol_drop20 | 12.5% | −34.1% | 0.46 | 47 | −6.4 (−16.2 to −0.5) | 4% | +0.8 / −14.3 | +2.8 (−1.7 to +10.1) | −2.6 (−4.1 to −0.8) | reject |
| faber10_buy | 16.5% | −28.7% | 0.60 | 43 | −2.4 (−12.0 to +2.8) | 20% | −6.5 / +2.6 | +8.2 (−4.2 to +19.1) | −7.0 (−11.8 to −3.3) | reject |
| faber10_cash | 13.1% | −30.7% | 0.48 | 45 | −5.8 (−16.4 to +0.1) | 5% | −7.3 / −4.0 | +6.2 (−5.8 to +19.9) | −5.3 (−10.4 to −1.4) | reject |
| sma200_buy | 16.5% | −28.7% | 0.60 | 43 | −2.4 (−12.0 to +2.8) | 20% | −6.5 / +2.6 | +8.2 (−4.2 to +19.1) | −7.0 (−11.8 to −3.3) | reject |
| absmkt_cash | 14.5% | −36.9% | 0.51 | 43 | −4.4 (−12.7 to +2.0) | 14% | −7.1 / −1.0 | +0.0 (−7.8 to +6.5) | −7.1 (−12.8 to −2.3) | reject |
| bear24_buy | 18.1% | −36.9% | 0.61 | 49 | −0.8 (−2.8 to +0.4) | 28% | −1.7 / +0.2 | +0.0 (−2.0 to +0.0) | −0.6 (−1.5 to +0.0) | inconclusive |
| absstock | 18.5% | −38.3% | 0.62 | 50 | −0.4 (−2.5 to +2.2) | 38% | +1.1 / −2.2 | −1.4 (−2.7 to +1.4) | −0.0 (−0.7 to +0.5) | inconclusive |
| season_drop20 | 12.0% | −39.2% | 0.42 | 48 | −6.9 (−13.7 to −1.5) | 2% | −2.7 / −11.6 | −2.3 (−7.3 to +4.2) | −1.9 (−3.4 to −0.7) | reject |
| str_drop10 | 13.6% | −35.1% | 0.49 | 49 | −5.3 (−12.0 to +0.5) | 7% | −0.8 / −10.3 | +1.8 (−3.7 to +6.2) | −0.8 (−2.5 to +0.6) | reject |
| max_drop20 | 14.7% | −33.5% | 0.53 | 46 | −4.1 (−11.3 to +0.1) | 5% | −1.9 / −6.7 | +3.4 (−1.1 to +8.7) | −3.4 (−4.7 to −1.9) | reject |
| gap15_buy | 14.4% | −35.0% | 0.51 | 48 | −4.5 (−11.5 to +0.3) | 6% | −0.1 / −9.5 | +1.9 (−1.3 to +6.0) | −1.9 (−3.1 to −0.7) | reject |
| gap15_both | 12.8% | −35.0% | 0.46 | 50 | −6.1 (−14.2 to −0.5) | 3% | −2.1 / −10.6 | +1.9 (−2.9 to +6.2) | +0.4 (−1.2 to +2.2) | reject |
| r2_drop20 | 18.9% | −36.7% | 0.63 | 50 | −0.0 (−1.5 to +1.4) | 44% | −0.1 / +0.0 | +0.2 (−1.2 to +0.9) | −0.1 (−0.5 to +0.2) | inconclusive |
| **industry_top** | 22.0% | −37.3% | 0.72 | 47 | +3.1 (−2.1 to +8.6) | 84% | +3.4 / +2.7 | −0.4 (−3.5 to +3.8) | −2.6 (−4.3 to −1.5) | **shadow** |
| industry_top6m (neighbour) | 18.2% | −36.2% | 0.61 | 48 | −0.7 (−5.1 to +2.9) | 36% | −1.3 / −0.0 | +0.7 (−3.2 to +3.3) | −2.1 (−3.4 to −1.0) | reject |
| industry_top_both (neighbour) | 23.4% | −37.3% | 0.76 | 50 | +4.6 (−1.3 to +11.2) | 90% | +3.3 / +6.0 | −0.5 (−3.7 to +3.7) | +0.6 (−1.4 to +2.1) | (shadow) |

Walk-forward by family (each year from 2022: the best Sharpe on the years
before, of live and the family's variants):

| Family | Δ a year vs live (90% range) | Ahead in | Picks 2022 → 2026 |
|---|---|---|---|
| fip | −2.3 (−6.1 to +1.7) | 18% | pool40, pool40, drop20, drop20, drop20 |
| high52 | −2.4 (−5.7 to +0.1) | 6% | gh_pool40, gh_pool40, live, gh_pool40, live |
| residual | −2.1 (−6.1 to +1.1) | 13% | resid_pos throughout |
| volatility | −4.0 (−7.6 to −1.2) | 1% | vol_drop20, vol_drop20, live, live, live |
| market | −2.5 (−7.3 to +1.4) | 16% | faber10_buy, then live |
| absolute | −1.4 (−2.7 to −0.4) | 2% | absstock ×3, live ×2 |
| seasonality | 0.0 | — | live throughout (identical) |
| reversal | −4.0 (−7.8 to −0.7) | 1% | str_drop10 ×2, live ×3 |
| max | −3.5 (−7.5 to −0.6) | 2% | max_drop20 ×2, live ×3 |
| clenow | −1.6 (−3.5 to −0.4) | 1% | r2_drop20, gap15_buy, live ×3 |
| industry (before the neighbours were added) | +1.8 (−3.5 to +7.8) | 70% | industry_top ×3, live, industry_top |
| industry (with the neighbours) | +5.1 (−1.5 to +13.3) | 88% | industry_top ×3, industry_top_both ×2 |

The neighbours were added after industry_top passed, to test whether the
result depends on its exact rule. They were not candidates in their own right,
so the second industry row is contaminated by that choice.

Market gates were risk-off at these signals:

| Gate | Signals | Months |
|---|---|---|
| Faber 10-month SMA | 16 | Feb–Apr 2020, Feb 2022, Apr–Oct 2022, Dec 2022, Oct 2023, Mar–Apr 2025, Mar 2026 |
| 200-day SMA | 16 | the same 16 months at every month end of the sample, hence the identical rows |
| 12-month return negative | 14 | Mar–Apr 2020, Apr 2022–Mar 2023 |
| 24-month return negative | 2 | Mar 2020, Oct 2023 |

The volatility overlay held 88% of the book on average, 31% at its lowest (Aug
2020).

Calendar years, live against industry_top: 2020 22.9 vs 25.2; 2021 20.9 vs
23.3; 2022 −8.5 vs −3.6; 2023 13.5 vs 16.4; 2024 44.4 vs 28.3; 2025 21.3 vs
29.2; 2026 (Jan–Oct) 18.3 vs 32.6. It is ahead in 6 of 7 years and 16 pts
behind in 2024.

## The candidates: literature, fit and result

Each entry says what was verified in this session and how.

- **Verified (paper):** read in the paper itself (author-hosted or NBER PDF).
- **Verified (abstract):** checked against the abstract or a bibliographic
  record, with the method from a secondary source.
- **Not verified:** written from memory. Check it before you quote it.

### 1. Frog in the Pan: information discreteness (FIP)

- **Definition:** ID = sgn(PRET) × (%neg − %pos).
  - PRET is the cumulative return over the past twelve months, skipping the
    most recent month.
  - %neg and %pos are the shares of DAILY returns in that window below and
    above zero. Zero-return days count in the denominator.
  - Lower is better: −1 is a winner that rose almost every day ("continuous
    information").
  - `filters.frog_in_the_pan(close, 252, 21)`.
- **Source:** Da, Gurun & Warachka (2014), "Frog in the Pan: Continuous
  Information and Momentum", *Review of Financial Studies* 27(7), 2171–2218.
  **Verified (paper):** equation (1), the daily returns, the 12-month window
  skipping a month and the sign convention, from the author-hosted PDF
  (www3.nd.edu/~zda/Frog.pdf).
- **Evidence:** CRSP, 1927–2007. Sorting first on PRET and then on ID,
  six-month-holding momentum rises from −2.07% (discrete) to 5.94%
  (continuous), and it does not reverse in the long run.
- **Gray & Vogel's use:** *Quantitative Momentum* (Wiley, 2016) keeps the
  better half by FIP among the top decile by 12–2 momentum. **Verified
  (abstract):** their 1,000 → 100 → 50 screen is quoted from Alpha Architect's
  index presentation, 30 Sep 2019 (aaii.com). Alpha Architect's later R-code
  article computes the same measure from MONTHLY returns. The book's own text
  was not read, so whether the book uses daily or monthly returns is not
  verified. This code follows the paper.
- **Fit:** a tie-break (`fip_pool40`: new buys by FIP among the top 40), a
  relative buy gate (`fip_drop50`, `fip_drop20`) and a buy-and-keep gate
  (`fip_drop20_both`).
- **Weaknesses:**
  - It needs a winner set to condition on. Ours is the top of a risk-adjusted
    score, which already favours smooth paths, so ID has little left to add.
  - It ignores the size of daily moves.
  - The published sample ends in 2007.
- **Result: inconclusive.** The halves disagree for all four variants: the
  first half is ahead, the second behind. The pool raises turnover by 7 pts.
  The walk-forward is −2.3 pts a year.

### 2. 52-week-high proximity

- **Definition:** close ÷ highest price of the past 52 weeks.
  `filters.fifty_two_week_ratio` uses closes, as the live gate does (≥ 0.80).
- **Source:** George & Hwang (2004), "The 52-Week High and Momentum
  Investing", *Journal of Finance* 59(5). **Verified (abstract):** nearness to
  the high predicts returns better than past returns and does not reverse;
  CRSP, July 1963 – December 2001; winners are the top 30% by the ratio.
  International replications are mixed.
- **Fit:** the strategy already has it as a gate. Tested: a tighter gate,
  within 10% (`high90`); and a tie-break, new buys by nearness among the top 40
  (`gh_pool40`).
- **Weaknesses:**
  - It mostly duplicates the score: a stock near its high has a high 12-month
    return.
  - A tighter gate cuts the qualified list.
- **Result: reject (both).**
  - `high90`: behind in both halves, −2.5 pts a year.
  - `gh_pool40`: −1.1, ahead in only 20% of draws, though max drawdown is
    4.4 pts better.
  - Paresh's regime study (12 Oct 2026) found the 10% rule helped only in
    uptrends.

### 3. Residual (idiosyncratic) momentum, as a gate only

- **Definition, as published:** regress each stock's monthly returns on the
  Fama-French three factors over 36 months. Score it on the residuals of
  months t−12 to t−2, divided by their standard deviation.
- **Definition, here:** `filters.residual_score` uses one factor (the
  benchmark, SPTM), daily returns, a beta from a rolling 756 sessions, and
  mean(e)/sd(e) over 252 sessions skipping 21.
- **Source:** Blitz, Huij & Martens (2011), "Residual Momentum", *Journal of
  Empirical Finance* 18(3), 506–521. **Verified (abstract):** the citation and
  the idea. The 36-month three-factor construction is from Quantpedia's
  summary; the paper was not read.
- **Evidence:** about the same return as total-return momentum at about half
  the volatility, and smaller crashes (secondary summaries: gross Sharpe about
  0.90 against 0.45). Huij & Lansdorp (2017) revisit it.
- **Fit:** the residual RANKING was removed from the original terminal and is
  not brought back. Tested as a buy gate only: not in the worse half of the
  qualified (`resid_drop50`), and residual score above zero (`resid_pos`).
- **Weaknesses:**
  - One factor, not three: a value or size tilt stays in e.
  - The beta is noisy.
  - Between 2020 and 2026 the market factor's beta around COVID was unstable.
- **Result: inconclusive.** −2.3 and −0.6 pts a year. The halves disagree.
  Max drawdown is 1.6–2.4 pts worse. The walk-forward is −2.1.

### 4. Volatility-managed momentum and momentum crashes

- **Barroso & Santa-Clara (2015)**, "Momentum Has Its Moments", *Journal of
  Financial Economics* 116(1), 111–120.
  - **Rule:** scale the long-short momentum portfolio by target ÷ its realised
    volatility over the past six months (126 days); a 12% target.
  - **Verified (abstract):** it "virtually eliminates crashes and nearly
    doubles the Sharpe ratio". The 0.53 → 0.97 figure is from a summary of the
    working paper.
- **Daniel & Moskowitz (2016)**, "Momentum Crashes", *Journal of Financial
  Economics* 122(2), 221–247.
  - Crashes come in panic states: after market declines and when volatility
    is high, as the market rebounds.
  - **Verified (paper, NBER w20439):** their bear-market indicator is 1 when
    the cumulative CRSP value-weighted return over the past 24 months is
    negative; market variance is measured over the preceding 126 days.
- **Fit:** a long-only, 20-stock book has no short leg that crashes, and both
  papers are about the long-short portfolio. Tested in three forms:
  - `vol_target`: the book's exposure is set at each month end to
    min(1, the median of its own past volatility ÷ its 126-day volatility). The
    rest is held in cash at 0%, exposure changes are charged the 10 bps, and
    there is no leverage. It is an overlay on the live book's daily returns:
    estimated from a 2019 warm-up run, never reported before 2020.
  - `vol_drop20`: a stock-level buy gate that drops the most volatile 20% of
    the qualified.
  - `bear24_buy`: a market gate, no new buys in a bear market.
- **Weaknesses:**
  - The overlay is not the papers' strategy, and it needs a target.
  - Cash at 0% understates it when T-bills paid 5% (2023–24).
  - A drop of qualified names is a tilt toward low volatility, which momentum
    winners are not.
- **Result: reject (`vol_target`, `vol_drop20`); inconclusive
  (`bear24_buy`).**
  - `vol_target`: −5.4 pts a year, ahead in 3% of draws; drawdown 2.6 pts
    better. It cut exposure to 31% in August 2020 and missed the rebound.
  - `vol_drop20`: −6.4; behind by 14 pts a year in the second half.
  - `bear24_buy` was risk-off at only two signals (March 2020, October 2023):
    too few to judge.

### 5. Market trend and absolute momentum

- **Faber (2007)**, "A Quantitative Approach to Tactical Asset Allocation",
  *Journal of Wealth Management* (Spring 2007). Hold an asset only while its
  month-end price is above its 10-month simple average; otherwise cash.
  Tested on US equities from 1900. **Verified (abstract):** from secondary
  descriptions; the paper was not fetched.
  - `filters.faber_trend`.
  - `faber10_buy`: no new buys while off.
  - `faber10_cash`: all cash while off.
- **Clenow's index filter:** buy only while the S&P 500 is above its 200-day
  average (`sma200_buy`). It gave the same 16 risk-off month ends as Faber's in
  this sample, so the results are identical.
- **Time-series momentum and absolute momentum:**
  - Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum", *Journal of
    Financial Economics* 104(2), 228–250: an asset's own 12-month excess return
    predicts its next month, across 58 futures. **Not verified** in this
    session.
  - Antonacci, *Dual Momentum Investing* (McGraw-Hill, 2014) and "Risk Premia
    Harvesting Through Dual Momentum" (2012/13): the asset's 12-month return
    against T-bills. **Verified (abstract):** the rule. The journal and year of
    the paper are uncertain (sources disagree).
  - Tested at market level: `absmkt_cash`, all cash while the S&P 1500's
    12-month return is negative. The hurdle is 0, not the T-bill return: no
    T-bill series is in the store.
  - Tested at stock level: `absstock`, a buy gate requiring the stock's own
    12-month return above 4%.
- **Cooper, Gutierrez & Hameed (2004)**, "Market States and Momentum",
  *Journal of Finance* 59(3), 1345–1365. Momentum earned 0.93% a month after a
  non-negative 3-year market return and −0.37% after a negative one,
  1929–1995. **Verified (abstract).** Not run separately: the 3-year return
  of the S&P 1500 was never negative at a 2020–2026 signal; the 24-month gate
  above is the nearer test.
- **Weaknesses:**
  - Trend gates on the market help in long bear markets (2000–02, 2008), and
    there was none in 2020–26. The sample cannot test them fairly.
  - They whipsaw in V-shaped falls (2020, 2025).
  - The live book's own EMA and 52-week gates already empty it in a broad fall.
- **Result: reject (all four market gates); inconclusive (`absstock`).**
  - The trend gates cut max drawdown by 6–8 pts and turnover by 5–7, at a cost
    of 2.4–5.8 pts a year: they missed the 2020 rebound and were whipsawed in
    2022. Behind in 80–95% of draws.
  - `absstock` almost never binds on winners: −0.4, halves disagree.
  - The owner may still value the drawdown cut. That is a preference, not
    something this test can settle: **owner decision**.

### 6. Seasonality

- **Gray & Vogel:** rebalance quarterly at the end of February, May, August
  and November, ahead of quarter-end window dressing, not at calendar quarter
  ends. 1927–2014: CAGR 15.97% against 15.06%, Sharpe 0.60 against 0.57.
  **Verified (abstract):** quoted from Alpha Architect's 2019 presentation.
  - **Not tested:** it is a quarterly schedule, and the owner's framework is
    monthly with March/September resets.
- **Heston & Sadka (2008)**, "Seasonality in the Cross-Section of Stock
  Returns", *Journal of Financial Economics* 87(2), 418–445. A stock's return
  in a calendar month predicts its return in the same month of later years, at
  annual lags up to 20 years; NYSE/AMEX 1963–2002. **Verified (abstract).**
  - `filters.same_month_seasonality`: the average return in the coming
    calendar month over the past 10 years, at least 5 observed.
  - Tested as `season_drop20`.
- **Weaknesses:**
  - Each stock has 10 observations per calendar month: noisy.
  - In the paper the effect is a long-short spread across all stocks, not a
    filter among winners.
- **Result: reject.** −6.9 pts a year, behind in both halves, ahead in 2% of
  draws.

### 7. Short-term reversal and the skip month

- **Source:**
  - Jegadeesh & Titman (1993), "Returns to Buying Winners and Selling Losers",
    *Journal of Finance* 48(1), 65–91: skip a week between formation and
    holding, because of one-month reversal.
  - Jegadeesh (1990): the one-month reversal itself.
  - **Not verified** in this session (standard references).
  - Most academic momentum skips the last month (12–2); Da et al. and Gray &
    Vogel do too.
- **Fit:** the live score has no skip month and puts 10% on the 1-month
  window. Removing that would change the score, which is out of scope here.
  Paresh's lookback study (12 Oct 2026) found 1M weights of 50% or more worse
  and 0% no reliably better. Tested as a gate instead: `str_drop10` does not
  buy the 10% of the qualified with the highest 1-month return.
- **Weaknesses:**
  - Reversal is strongest in small, illiquid stocks; the S&P 1500 has few.
  - The gate removes the names the 3- and 6-month windows like most.
- **Result: reject.** −5.3 pts a year, behind in both halves.

### 8. Maximum daily return (lottery stocks)

- **Definition:** MAX = the largest daily return in the previous month.
  `filters.max_daily_return(close, 21)`.
- **Source:** Bali, Cakici & Whitelaw (2011), "Maxing Out: Stocks as
  Lotteries and the Cross-Section of Expected Returns", *Journal of Financial
  Economics* 99(2), 427–446. **Verified (abstract):** the gap between the
  lowest and highest MAX deciles exceeds 1% a month, raw and risk-adjusted.
  The working paper gives −1.03% raw and −1.18% four-factor alpha.
- **Fit:** a buy gate, `max_drop20`.
- **Weaknesses:**
  - Among recent winners a high MAX is often news, such as earnings or a
    guidance raise, that momentum then continues.
  - A 2022 *Critical Finance Review* note attributes the effect to
    overreaction in general.
- **Result: reject.** −4.1 pts a year, behind in both halves; max drawdown
  3.4 pts better.

### 9. Clenow, *Stocks on the Move* (2015)

- **Rules, as secondary sources describe them:**
  - rank by the annualised slope of a 90-day regression of log price on time,
    times its R-squared;
  - disqualify a stock with a gap over 15% in the last 90 days;
  - hold only above its 100-day average;
  - buy only while the S&P 500 is above its 200-day average;
  - size by ATR;
  - trade weekly.
  - **Verified (abstract):** from QuantConnect implementations and reviews.
    The book was not read; sources differ on details (the gap rule, the ATR
    window).
- **Fit:** the ranking and the sizing conflict with the framework and are not
  used. Tested:
  - the gap rule, close-to-close because the engine has closes, not opens:
    `gap15_buy` and `gap15_both`;
  - trend quality as a gate, `r2_drop20`: not in the worst 20% of the
    qualified by 90-day R-squared. The score still has no R-squared in it;
  - the index filter, under section 5.
- **Weaknesses:**
  - Close-to-close moves are not gaps.
  - A 15% move in the S&P 600 is often an earnings reaction.
- **Result: reject (gap); inconclusive (R-squared).**
  - The gap gate costs 4.5–6.1 pts a year.
  - `r2_drop20` changes almost nothing (−0.0), because the Sharpe score
    already prefers smooth trends.

### 10. Industry momentum

- **Definition:** each GICS sector's equal-weight 12-month return over the
  stocks on file. `industry_top` is a buy gate: only names whose sector is in
  the stronger half of the 11 sectors (`filters.industry_momentum`).
- **Source:** Moskowitz & Grinblatt (1999), "Do Industries Explain
  Momentum?", *Journal of Finance* 54(4), 1249–1290. **Verified (abstract):**
  industry momentum explains much of stock momentum, and industry strategies
  are more profitable than stock strategies.
- **Fit:** a buy gate (or buy and keep). It interacts with the 40% sector cap:
  the gate concentrates the book in fewer sectors, and the cap still binds.
- **Weaknesses:**
  - 11 sectors is coarse; the paper used 20 industries.
  - Today's labels are applied to the past.
  - The sectors' averages are over today's members only, so survivors set the
    sector ranking too. This is exactly the bias the rerun must remove.
  - The 6-month version fails (−0.7, reject), so the result depends on the
    window.
- **Result: shadow, weakly.**
  - +3.1 pts a year (90% range −2.1 to +8.6), ahead in both halves (+3.4 /
    +2.7) and in 84% of draws.
  - Max drawdown −0.4 pts; turnover −2.6 pts.
  - Walk-forward +1.8 (before the neighbours).
  - It is the one pass in 23, near the threshold, and the neighbour on 6-month
    returns fails.
  - Rerun it on point-in-time membership before recording it forward.

### Not tested, and why

- **Trading volume** (Lee & Swaminathan 2000, "Price Momentum and Trading
  Volume", *Journal of Finance* 55(5), 2017–2069; abstract verified): low-volume
  winners continue longer. It needs turnover (volume ÷ shares outstanding), and
  run_backtest carries closes only. Possible later, from `data/prices` Volume
  and market caps.
- **Intermediate momentum** (Novy-Marx 2012, "Is Momentum Really Momentum?",
  *Journal of Financial Economics* 103(3); **not verified**): returns 12–7
  months ago predict better than 6–2. This is a change of weights, not a
  filter; Paresh's lookback study covers that question.
- **Earnings momentum and analyst revisions** (Chan, Jegadeesh & Lakonishok
  1996): no earnings data in the store.
- **Gray & Vogel's seasonal quarterly schedule:** section 6.

## Recommendation per filter (for the owner)

| Filter | Recommendation | Why |
|---|---|---|
| Sector momentum gate (12-month, top half) | **Shadow, after a point-in-time rerun** | The only pass; narrow; the 6-month neighbour fails |
| FIP (all four forms) | Inconclusive | Halves disagree; no gain over the Sharpe score |
| Residual momentum gate | Inconclusive | Halves disagree; worse drawdown |
| Trend R-squared gate | Inconclusive | Changes nothing |
| Absolute momentum (stock) | Inconclusive | Rarely binds on winners |
| Bear-market gate (24 months) | Inconclusive | Two risk-off signals in the sample |
| 52-week high tighter or as tie-break | Reject | Behind in both halves |
| Volatility overlay and volatility gate | Reject | −5 to −6 pts a year |
| Market trend gates (Faber, 200-day, 12-month) | Reject on return | Drawdown 6–8 pts better: owner's call whether that is worth 2–6 pts a year |
| Seasonality (same month) | Reject | −6.9 pts a year |
| Short-term reversal gate | Reject | −5.3 pts a year |
| MAX (lottery) gate | Reject | −4.1 pts a year |
| Clenow gap gate | Reject | −4.5 to −6.1 pts a year |

Nothing here changes the live record, and the record's settings are the
owner's decision.

## Not verified

- **Membership:** every number above is on today's list. Rerun on the
  point-in-time file (baseline 2019-12-31 or earlier) once it is built:

  ```
  python scripts/research_filters.py run --out DIR --membership path/to/membership_history.json
  python scripts/research_filters.py report --out DIR
  ```

  Former members are loaded from the price store when it has them, and the
  report counts those it lacks.
- **Primary texts not read:**
  - Gray & Vogel's book: the definition of FIP there (daily or monthly
    returns).
  - Clenow's book.
  - Faber's, Antonacci's and Blitz et al.'s papers.
  - Moskowitz, Ooi & Pedersen, Jegadeesh & Titman and Novy-Marx: written from
    memory.
- **Simplifications:**
  - Cash earns 0% in the backtester, which understates the market gates and
    the overlay in 2023–24.
  - Residual momentum uses one factor.
  - Clenow's gaps are close-to-close.
  - The sector labels are today's.
- **Sample:** 2020–2026 has no long bear market, so it cannot test the trend
  gates' main claim.
