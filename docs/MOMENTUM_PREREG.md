# Momentum improvements: pre-registration (10 Nov 2026)

This document fixes, **before any test is run**, which improvements from the momentum literature
will be tested on the US book, exactly how each one is computed, how it plugs into the book, and
what counts as a pass. Anyone implementing it should not need to make a choice after seeing a
result. Where the paper leaves a choice open, this document makes it and says so ("our choice").

It builds on `docs/RESEARCH_FILTERS.md` (23 variants already tested on today's S&P 1500 list:
one narrow pass, the 12-month sector-momentum buy gate) and `docs/MOMENTUM_EVIDENCE.md`
(post-2000 large-cap momentum is weak: French "Big Hi" minus market +0.55% a year since 2000,
MSCI USA Momentum +0.44% a year live 2014-2025). **The base expectation for any one of these
improvements is a small gain or none.** Published anomaly returns fall 26% out of sample and
58% after publication (McLean & Pontiff 2016), and the strongest factors decay the most.

## Contents

1. The book being improved
2. Data each candidate needs, and checks to run first
3. How every test is run and judged (fixed now)
4. The candidates (30), with sources, rules, fit, evidence, failure modes, computability
5. Not testable with this data
6. Ranking by strength of evidence for US large-cap long-only use
7. **The shortlist (7 tests) and 2 combinations**, fully specified
8. What was not checked

How to read the source tags:

- **[full text]**: I read the method and the numbers in the paper itself (PDF converted to text in
  this session). For working papers the version is named.
- **[abstract]**: I saw only the abstract or a publisher/bibliographic page.
- **[secondary]**: I saw it only in someone else's summary (CXO Advisory, Quantpedia, Alpha
  Architect, a search summary). **Not verified.**
- **[memory]**: from prior knowledge, not checked in this session. **Not verified.**

---

## 1. The book being improved

As given by the owner for this exercise:

- **Universe:** point-in-time S&P 500 members at each signal date.
- **Score:** blend of 1, 3, 6, 9 and 12-month volatility-adjusted returns, weights 10/30/30/20/10,
  winsorised cross-sectional z-scores, no skip month (`src/engine/calendar_momentum.py`; that
  code's own definition of a window's volatility-adjusted return is used wherever this document
  says "vol-adjusted return over a window").
- **Book:** 20 stocks, 5% each, monthly. Signal at the month's last session, fill at the next
  session's close. A holding is kept while it ranks in the top 40.
- **Buy filters:** close above its 50-day EMA; close within 20% of its 52-week high.
- **Caps:** 5% a stock, 40% a GICS sector.
- **Costs:** 10 bps a round trip.

Note: `docs/RESEARCH_FILTERS.md` says the live record adds a six-monthly reset (March and
September) with a 15% hold cap from the 30 Nov 2026 signal. **Primary runs use the configuration
above (no reset).** If the owner wants the reset configuration instead, that must be decided
before the first run and applied to the base and every variant alike.

Already tested and not repeated as is: FIP drop-worse-half (and pool/drop20 forms), 52-week-high
nearness (tighter gate, tie-break), one-factor residual-momentum gate, volatility-target overlay
without leverage (book's own volatility, remainder in cash), Faber 10-month gate, 200-day gate,
12- and 24-month market gates, stock absolute momentum (> 4%), sector-momentum gate (12-month
passed; 6-month failed), Clenow gap and R-squared gates, MAX, short-term reversal (drop the top
10% by 1-month return), same-month seasonality.

---

## 2. Data each candidate needs, and checks to run first

| Input | Where from | Used by | Check before use |
|---|---|---|---|
| Daily adjusted close, high, low, volume, 2008- | price store | all | Volume is split-adjusted the same way as price (Yahoo volume is; confirm on 3 known splits: AAPL 2014 and 2020, NVDA 2024). |
| Point-in-time S&P 500 membership | `data/membership_monthly.csv` | all | Baseline date before the first signal; count of former members with no prices (report it; they are a survivorship leak). |
| GICS sector | store | caps, C2 | Labels are today's; flag it. |
| Market cap today | store | S4 (turnover proxy) | Same date as the close used to back out shares. |
| S&P 500 index level | store | S2, S3, C1 | Price index only, no dividends. |
| **SPY adjusted close** (total return) | same price source as stocks | S2, S3, C1 (the non-momentum sleeve) | If unavailable, use the S&P 500 price index and state that the sleeve is understated by its dividend yield (about 1.3-2% a year times the average sleeve weight). |
| French FF3 monthly (Mkt-RF, SMB, HML, RF) | `F-F_Research_Data_Factors.zip` | S1, C1, C2 | Record the CRSP vintage in the file header (e.g. 202609) and the download date; freeze the file. French revises history. |
| French daily Mkt-RF, RF | `F-F_Research_Data_Factors_daily.zip` | S3 | same |
| French daily momentum (UMD/Mom) | `F-F_Momentum_Factor_daily.zip` | S2, S3, C1 | same |
| French monthly momentum | `F-F_Momentum_Factor.zip` | S3 (estimation) | same |

**Publication lag rule (applies to every French series):** French publishes with a lag of a
month or more. At a signal at the end of month m, only French data through the end of month
**m−1** may be used. This is a departure from the papers (they use data through m) and is our
choice, to keep the backtest real-time. Live use needs the same rule; if month m−1 is not yet
published at the signal date, use the latest published month and log it.

**Sample start:** daily data begin in January 2008, so the first complete monthly stock return is
February 2008 (our assumption; confirm from the store). S1 needs 36 monthly returns ending in m−1,
so its first signal is the end of February 2011 (with data from 2 Jan 2008). **Every variant and
the base are evaluated on the same sessions, from the first fill after the first month-end at
which every shortlisted variant can be computed** (expected: early March 2011).

---

## 3. How every test is run and judged (fixed now)

### 3.1 Runs

- **Primary sample:** first common fill (expected March 2011) to the end of the last complete
  month on the day the tests are run. Write the end date in the results; do not move it.
- **Secondary sample:** January 2020 to the same end date (the owner's earlier preference was no
  backtest before 2020; if the owner wants 2020+ as primary, swap them before the first run).
- **Membership:** point-in-time S&P 500 only. A run on today's list is not a valid result for
  this pre-registration.
- **Rebalance-offset ensemble (against timing luck, see C21):** the base and every variant are run
  four times, with the signal at the session 0, 5, 10 and 15 sessions before the month's last
  session (fill at the next close). The **primary statistic is the mean over the four offsets** of
  the variant-minus-base difference; each offset is also reported. Hoffstein, Faber & Braun (2020)
  measure timing luck of 4.2% a year for a 50-stock quarterly US large-cap momentum book; a
  20-stock monthly book's single-schedule result is a noisy draw.
- **Costs:** 10 bps a round trip on every trade, including trades between the book and the SPY
  sleeve. Sensitivity: 20 bps.
- **Cash** (where any) earns 0; none of the shortlisted variants holds cash.

### 3.2 Statistics

For each variant, against the base on the same sessions:

1. Return a year (CAGR), max drawdown, volatility, Sharpe (excess of French RF), turnover a year,
   tracking error and information ratio against SPY.
2. Halves: the CAGR gap in each half of the primary sample (split at the middle session).
3. Paired block bootstrap: 63-session blocks, 2,000 draws, seed 20261110. 90% range of the CAGR
   gap, the Sharpe gap and the max-drawdown gap; share of draws in which the variant is ahead.

**Primary metric by kind:**

- Selection changes (S1, S4, S6, S7, C2): CAGR gap.
- Exposure overlays (S2, S3, C1): Sharpe gap; CAGR and max drawdown reported beside it. An
  overlay that lowers risk and return proportionally is not an improvement.
- Tranching (S5): it is not expected to raise return. Primary: the dispersion of CAGR across the
  four offsets (timing luck), against the base's dispersion.

### 3.3 Verdicts (fixed now)

- **Pass (candidate for a forward shadow, owner's decision):** all of
  1. ahead on the primary metric in both halves;
  2. ahead in at least 90% of bootstrap draws (stricter than the 80% used before, because nine
     tests are run; with nine roughly independent tests at a one-sided 10% level, about one false
     pass is expected by luck);
  3. ahead on the primary metric at all four offsets, and at 20 bps;
  4. max drawdown no more than 2 pts worse; turnover no more than 15 pts a year higher.
  - S5 passes if the offset dispersion falls by at least a third and the mean CAGR is no more than
    0.5 pt a year lower.
- **Reject:** behind in both halves, or ahead in at most 20% of draws.
- **Inconclusive:** anything else.

### 3.4 Rules against post-hoc choice

- One specification per candidate. **No neighbours are added after a result is seen** (the
  industry_top neighbours in RESEARCH_FILTERS were added after it passed, which contaminated that
  family's walk-forward).
- All nine results are reported, whatever they show.
- A bug fix after a run is allowed only if it is to the specification written here; the fix and
  the before/after figures are both reported.
- Thresholds below are the source's own where it gives one; otherwise one round value, stated.

---

## 4. The candidates

Each entry: source and read status; rule as the source states it; fit to this book; reported
evidence; failure modes; computable or not.

### 4.1 Residual / idiosyncratic momentum

#### C01. Residual momentum, three-factor (Blitz, Huij & Martens 2011)

- **Source:** Blitz, D., Huij, J. & Martens, M. (2011), "Residual Momentum", *Journal of Empirical
  Finance* 18(3), 506-521. Accepted manuscript: https://repub.eur.nl/pub/22252/ResidualMomentum-2011.pdf
  **[full text]**.
- **Rule, as stated:**
  - Each month, for each stock, regress monthly excess returns on the Fama-French three factors:
    r_i,t = α_i + β1 RMRF_t + β2 SMB_t + β3 HML_t + ε_i,t, "over 36-month rolling windows, i.e.,
    over the period from t-36 until t-1". Only stocks with a complete 36-month history are
    included.
  - Score: the sum of residuals over months t-12 to t-2 (12-1M, skipping the latest month),
    "standardized by its standard deviation over the same period". The estimated α is **not**
    included in the residual (the paper explains why: it would import long-term reversal).
  - Deciles, equal-weighted, overlapping holding periods of 1, 3, 6, 12 months.
- **Evidence (US, 1930-2009, long-short, gross):**
  - 1-month holding, top minus bottom decile: total-return momentum 10.26% a year, volatility
    22.68%, Sharpe 0.45; residual momentum 11.20%, 12.49%, **Sharpe 0.90**.
  - Not standardised: 11.88%, 13.28%, Sharpe 0.89 (standardising mainly cuts risk).
  - **Long side only (winner decile, post-ranking):** total-return winners 21.31% a year,
    volatility 29.12%, Sharpe 0.73; residual winners **18.42%**, 24.54%, Sharpe 0.75. For a
    long-only book the gain is **lower volatility at about the same Sharpe, with a lower return**.
  - **Large caps** (the 10% largest stocks): Sharpe 0.36 (total) against 0.60 (residual), long-short.
  - 2000-2009: total-return momentum −8.5% a year, residual +4.7% a year (LS). The 2009 loss of
    total-return momentum came from its negative market beta in the rebound.
- **Fit:** a score blend (S1) or a better-specified gate. The earlier test used one factor
  (SPTM), daily returns and a 756-day beta; the paper uses three factors, monthly returns, 36
  months. Note the Paresh rule that removed systems (the residual-alpha RANKING) stay removed:
  a blend changes the score, which is the owner's decision. If the owner forbids score changes,
  run S1 as a buy gate instead (worse half of the qualified by the residual score not bought),
  specified now as the fallback.
- **Failure modes:** lower long-side return; needs 36 months of history (new members); French
  factors are all-CRSP, value-weighted; publication lag; the 2000s improvement is partly the
  2009 rebound, a single episode.
- **Computable:** yes (monthly returns from daily closes; French FF3 monthly).

#### C02. Idiosyncratic momentum, later evidence (Blitz, Hanauer & Vidojevic 2020)

- **Source:** Blitz, D., Hanauer, M. & Vidojevic, M. (2020), "The idiosyncratic momentum anomaly",
  *International Review of Economics & Finance* 69, 932-957; SSRN 2947044 (2017-2020).
  https://ssrn.com/abstract=2947044 **[secondary]** (CXO Advisory summary, 1 May 2017:
  https://www.cxoadvisory.com/momentum-investing/idiosyncratic-pure-or-residual-momentum-as-a-stock-return-predictor).
- **Rule:** the same as C01: FF3 betas from the prior 36 months; volatility-adjusted sum of
  monthly residuals over 12-1; size-split WML.
- **Evidence (US 1925-2015, LS, gross, secondary):** 1.39% a month against 1.54% for conventional
  momentum; monthly Sharpe 0.48 against 0.25; not explained by conventional momentum; works in
  every non-US region. Per the summary, it **trailed conventional momentum 1940-2000 and weakened
  after the early 2000s**, and took part of the 2009 crash.
- **Fit / computable:** as C01. It is corroboration of C01, not a separate test.

#### C03. Hanauer & Windmüller, "Enhanced Momentum Strategies" (2019 WP; JBF 2023)

- **Source:** Hanauer, M. & Windmüller, S., working paper of 14 Aug 2019,
  http://wp.lancs.ac.uk/mhf2019/files/2019/09/MHF-2019-076-Matthias-Hanauer.pdf **[full text]**;
  published version *Journal of Banking & Finance* 148 (2023) 106712,
  https://ideas.repec.org/a/eee/jbfina/v148y2023ics0378426622002928.html **[abstract]**.
- **Rule (iMOM):** FF3 regression on the past 36 months; cumulative 12-2 residual divided by the
  residuals' standard deviation (their eq. 9); 2×3 size × iMOM sort, NYSE-style 30/70 breakpoints
  on big stocks, value-weighted, monthly.
- **Evidence:** US 1930-2017 (long sample) and 48 countries 1991-2017. All of iMOM, constant
  volatility scaling and dynamic scaling roughly double the Sharpe ratio; US Sharpe 0.95 for
  dynamic (in-sample) scaling and for iMOM; iMOM cuts drawdowns most and gets the highest weight
  in max-Sharpe tests; **"the alpha stemming from volatility-scaling is distinctive from the
  idiosyncratic momentum alpha"**. LS, gross.
- **Caveat:** the **published abstract differs**: it compares only three volatility/dynamic-scaling
  strategies and says "no enhanced momentum strategy emerges as consistently superior". The
  iMOM comparison appears in the working paper only.
- **Fit:** supports S1 and the S1+S2 combination (C1).

#### C04. Market-model residual momentum (Chaves 2016; Gutierrez & Pirinsky 2007)

- **Sources:** Chaves, D. (2016), "Idiosyncratic momentum: U.S. and international evidence",
  *Journal of Investing* 25(2), 64-76 **[abstract/secondary]** (a regression that removes the
  market-beta component). Gutierrez, R. & Pirinsky, C. (2007), "Momentum, reversal, and the
  trading behaviors of institutions", *Journal of Financial Markets* 10(1), 48-75,
  https://ideas.repec.org/a/eee/finmar/v10y2007i1p48-75.html **[abstract only]**; Blitz et al.
  cite it for the standardisation.
- **Fit:** the one-factor version is what was already tested as a gate (inconclusive). Not
  repeated.

### 4.2 Volatility-managed and dynamic momentum

#### C05. Constant-volatility momentum (Barroso & Santa-Clara 2015)

- **Source:** Barroso, P. & Santa-Clara, P. (2015), "Momentum has its moments", *Journal of
  Financial Economics* 116(1), 111-120,
  https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 **[abstract]**. The
  formula is from a later paper that restates it (https://repositorio.ucp.pt/bitstreams/be7fa383-f5c7-406b-b753-4ea8e49d5d23/download)
  **[secondary]**; the original was not read.
- **Rule:** monthly variance forecast σ̂² = 21 × Σ_{j=0..125} r²_WML,d−j / 126 (realised variance of
  the past 126 daily WML returns); scaled weight on WML = σ_target / σ̂ with σ_target = 12% a
  year; leverage allowed.
- **Evidence:** "virtually eliminates crashes and nearly doubles the Sharpe ratio" [abstract];
  Sharpe 0.53 → 0.97, 1927-2011 [secondary]. Robust to 1, 3 or 6-month windows (as reported by
  Cederburg et al., below). LS.
- **Fit:** an exposure overlay. The earlier `vol_target` test scaled **the book's own volatility**,
  moved the remainder **to cash**, and targeted the book's median volatility: a different and
  weaker idea (RESEARCH_FILTERS, main-session review point 3). S2 below uses the paper's signal
  (the momentum factor's volatility) and moves the remainder **into SPY**, so it scales the
  momentum bet, not equity exposure.
- **Failure modes:** in a long-only book the crash comes mostly from the short side (Daniel &
  Moskowitz: crashes are "consistently driven by the conditional beta and option-like feature of
  losers"), so less is there to save; a 12% target with a cap of 1 keeps the book partly in SPY
  most of the time (UMD volatility 2010-2026 was 12.8%); costs of moving between book and SPY.
- **Computable:** yes (French daily UMD; SPY).

#### C06. Dynamic momentum (Daniel & Moskowitz 2016)

- **Source:** Daniel, K. & Moskowitz, T. (2016), "Momentum Crashes", *JFE* 122(2), 221-247; NBER
  WP 20439 (2014), https://www.nber.org/system/files/working_papers/w20439/w20439.pdf **[full text,
  working paper]**. Published version not read.
- **Rule, as stated:**
  - Optimal weight on WML: w*_{t−1} = (1/2λ) μ_{t−1} / σ²_{t−1}.
  - μ: fitted value of the regression of monthly WML returns on the interaction I_B,t−1 × σ̂²_m,t−1
    (with a constant), where I_B = 1 if the cumulative past two-year market return is negative,
    and σ̂²_m is the variance of daily market excess returns over the preceding 126 days.
  - σ²: a linear combination of a GJR-GARCH forecast (fitted by maximum likelihood on the full
    sample) and the realised standard deviation of the 126 daily WML returns before the month.
  - λ is chosen so the in-sample annualised volatility is 19%.
- **Evidence:** WML 1927-2013, Sharpe 0.71 static; dynamic "more than doubling its Sharpe ratio",
  and it beats constant-volatility momentum in spanning tests; across markets and asset classes
  combined, Sharpe 1.18. LS, gross. **The parameters are fitted on the full sample (in-sample).**
- **Fit:** an exposure overlay like C05 (S3 below), with the parameters estimated on French data
  1927-2007 and **frozen**, so 2011-2026 is genuinely out of sample.
- **Failure modes:** in-sample design in the paper; panic states are rare (2008-09 is outside
  the 2011+ sample except via its aftermath; 2020 and 2022 had I_B = 0 or briefly 1); the
  mechanism is about losers, which this book does not short.
- **Computable:** yes (French monthly UMD, daily UMD and daily market; SPY).

#### C07. Volatility-managed portfolios (Moreira & Muir 2017)

- **Source:** Moreira, A. & Muir, T. (2017), "Volatility-Managed Portfolios", *Journal of Finance*
  72(4), https://amoreira2.github.io/alan-moreira.github.io/VolPortfolios_published.pdf
  **[full text]**.
- **Rule:** f^σ_{t+1} = (c / σ̂²_t(f)) f_{t+1}, σ̂²_t = realised variance of daily returns in the
  previous month; c set so the managed and unmanaged series have the same unconditional
  standard deviation.
- **Evidence:** momentum factor 1926-2015, alpha of the managed factor on the unmanaged
  **12.51% a year** (s.e. 1.71), the largest of the factors. LS, gross, full-sample c.
- **Fit:** same family as C05. One-month variance is noisier; not tested separately.

#### C08. The critique: Cederburg, O'Doherty, Wang & Yan (2020)

- **Source:** "On the performance of volatility-managed portfolios", *JFE* 138(1), 95-117,
  https://www.lehigh.edu/~xuy219/research/COWY.pdf **[full text]**.
- **Finding:** across 103 strategies, real-time volatility-managed versions "do not systematically
  outperform" (53 better, 50 worse). **Exception:** "Volatility management improves performance
  for every momentum strategy, and five of the nine performance differences are statistically
  significant at the 5% level." Robust to alternative momentum definitions.
- **Related, not read:** Barroso & Detzel (2021), *JFE* 140, 744-767
  (https://econpapers.repec.org/RePEc:eee:jfinec:v:140:y:2021:i:3:p:744-767) **[abstract]**:
  after transaction costs, volatility management of factors other than the market "generally
  produces zero abnormal returns". Momentum-specific cost results not seen. Wang & Yan (2021),
  *JBF* 131, 106198 **[abstract/secondary]**: scaling by downside volatility beats total
  volatility in 89 of 94 anomalies. DeMiguel, Martín-Utrera & Uppal (2024), *JF* 79(6)
  **[abstract only]**: a multifactor version survives costs.
- **Consequence for the shortlist:** volatility management is the one improvement whose
  momentum-specific evidence survives the main out-of-sample critique, but all of it is
  long-short and costs may absorb it. S2 is therefore shortlisted; downside volatility is a
  reported robustness check of S2, not a separate test.

### 4.3 Confirmation from fundamentals or earnings

All need data the store does not have (earnings dates, EPS, analyst forecasts); see section 5.

### 4.4 Time-series and cross-sectional combinations

#### C09. Time-series and dual momentum in individual stocks (Lim, Wang & Yao 2018)

- **Source:** "Time-series momentum in nearly 100 years of stock returns", *JBF* 97, 283-296,
  https://eprints.lancs.ac.uk/id/eprint/128366 **[abstract/secondary]**.
- **Rule:** a stock's own past 12-month return sign; "dual momentum" requires both a positive own
  return and a cross-sectional winner rank. 1.88% a month in the 2016 draft [secondary]; a
  summary says dual stock momentum "does not perform well over the past 15 years or so".
- **Counter-evidence:** Goyal & Jegadeesh (2018, *RFS* 31(5)) [abstract]: the time-series edge is
  "largely due to" its time-varying net long position. Huang et al. (2020, *JFE* 135(3))
  [abstract]: asset-by-asset evidence is weak.
- **Fit:** already tested as `absstock` (inconclusive, rarely binds) and as market gates
  (rejected on return). The 50-day EMA buy filter is already a time-series element. Not repeated.

#### C10. Momentum turning points (Goulding, Harvey & Mazzoleni 2023)

- **Source:** *JFE* 149(3), 378-406, https://econpapers.repec.org/RePEc:eee:jfinec:v:149:y:2023:i:3:p:378-406
  **[abstract/secondary]**.
- **Rule:** blend slow (12-month) and fast (1-month) time-series signals; when they disagree
  (Correction or Rebound states, about 35% of months in US equities 1969-2018) scale to an
  intermediate speed.
- **Fit:** a market-level gate or exposure rule. Market gates were rejected on return in
  2020-26. Not shortlisted.

### 4.5 Factor, industry and intra-industry momentum

#### C11. Factor momentum (Ehsani & Linnainmaa 2022)

- **Source:** "Factor Momentum and the Momentum Factor", *Journal of Finance* 77(3), 1877-1919;
  NBER WP 25551 (Feb 2019), https://www.nber.org/system/files/working_papers/w25551/w25551.pdf
  **[full text, working paper]**.
- **Rule:** time-series factor momentum: long a factor whose return over months t-12 to t-1 is
  positive, short it if negative. "The average factor earns a monthly return of 1 basis point
  following a year of losses and 53 basis points following a positive year." Factor momentum
  spans UMD (UMD alpha 0.01% a month, t = 0.07) and also industry, industry-adjusted,
  intermediate and Sharpe-ratio momentum. Long-only "time-series winners": 5.9% a year, Sharpe
  1.35, 1963-2019 (later version, [secondary]).
- **Fit:** it is a rule for trading factors, not stocks. A stock-level adaptation (tilt toward
  stocks whose FF5 loadings align with factors in positive 12-1 momentum) would be our own
  invention, with no published test. **Not shortlisted.** It does explain why the book's
  score, which is "Sharpe ratio momentum" in their terms, works when it works.
- **Computable:** the factor series yes; the stock adaptation would need 36-month loadings (yes).

#### C12. Industry momentum (Moskowitz & Grinblatt 1999)

- **Source:** "Do Industries Explain Momentum?", *JF* 54(4), 1249-1290,
  https://econpapers.repec.org/RePEc:bla:jfinan:v:54:y:1999:i:4:p:1249-1290 **[abstract]**; the
  construction as restated by Ehsani & Linnainmaa **[full text of E&L]**: 20 industries, ranked
  on prior **six-month** returns, long the top three and short the bottom three.
- **Fit:** already tested on 11 GICS sectors as a buy gate: 12-month top half passed narrowly on
  today's list; the 6-month version (the paper's horizon) failed. The store has GICS sectors,
  not the 20 SIC-based industries, so the paper's own spec cannot be built. **Not re-tested as a
  new candidate;** the 12-month gate enters only as the pre-specified partner in combination C2,
  and its point-in-time rerun is TODO B18's job.

#### C13. Intra-industry / sector-neutral momentum (Cohen & Polk; Asness, Porter & Stevens 2000)

- **Sources:** industry-adjusted momentum (stock return minus its industry's) as restated by
  Ehsani & Linnainmaa **[full text of E&L]**; Ehsani, Harvey & Li (2023), "Is Sector Neutrality
  in Factor Investing a Mistake?", *Financial Analysts Journal* 79(3), 95-117,
  https://people.duke.edu/~charvey/Research/Published_Papers/P165_Is_sector_neutrality.pdf
  **[full text]**.
- **Evidence:** Ehsani, Harvey & Li: "omitting the sector component is more likely to improve the
  long-short factor and degrade the long-only factor"; and "unlike most of the other factors, the
  long-short momentum degrades from sector neutrality".
- **Fit:** a sector-demeaned score would remove the across-sector bet, which is the one part that
  passed (the sector gate). The literature says this hurts long-only momentum. **Not
  shortlisted.**

### 4.6 Quality of the path

#### C14. Frog in the Pan, exact formula (Da, Gurun & Warachka 2014)

- ID = sgn(PRET) × (%neg − %pos), daily returns over months t-12 to t-2; lower is better. Verified
  against the paper in RESEARCH_FILTERS. The code matches. **Already tested; not repeated.** A
  main-session replication on today's list found the opposite sign (smooth minus jumpy winners
  −0.57% a month), probably survivorship; the point-in-time rerun decides it.

#### C15. Consistency of winners (Grinblatt & Moskowitz 2004)

- **Source:** "Predicting stock price movements from past returns: the role of consistency and
  tax-loss selling", *JFE* 71(3), 541-579,
  https://econpapers.repec.org/RePEc:eee:jfinec:v:71:y:2004:i:3:p:541-579 **[abstract]**.
- **Rule [memory, not verified]:** a dummy for a high fraction of positive months (e.g. 8 or more
  of the past 12). It is FIP on monthly returns. **Not shortlisted** (overlaps FIP and the
  risk-adjusted score).

#### C16. Idiosyncratic volatility (Ang, Hodrick, Xing & Zhang 2006; Arena, Haggard & Yan 2008)

- **Sources:** Ang et al., *JF* 61(1) [memory]: IVOL = standard deviation of daily FF3 residuals
  over the past month; the highest-IVOL quintile earns low returns. Arena, Haggard & Yan (2008),
  "Price momentum and idiosyncratic volatility", *Financial Review* 43(2), 159-190,
  https://econpapers.repec.org/RePEc:bla:finrev:v:43:y:2008:i:2:p:159-190 **[abstract]**:
  **momentum returns are higher among high-IVOL stocks**; McLean (2010) finds no relation
  [secondary].
- **Fit:** a gate that drops high-IVOL winners would remove the names where momentum is
  strongest, per Arena et al. A total-volatility version (`vol_drop20`) was rejected at −6.4 pts.
  **Not shortlisted.**

#### C17. Acceleration (Chen, Yu & Wang 2017)

- **Source:** Chen, L.-W., Yu, H.-Y. & Wang, W.-K. (2017), "Evolution of Historical Prices in
  Momentum Investing", SSRN 3009059 (working paper) **[secondary]** (CXO Advisory, 22 Aug 2017:
  https://www.cxoadvisory.com/momentum-investing/acceleration-stock-momentum-strategy/).
- **Rule:** fit a quadratic in time to each stock's daily prices over the past 12 months; the
  coefficient on the squared term is the acceleration; within past-return quintiles, buy
  accelerating winners. One-month skip, six-month overlapping holding, value-weighted.
- **Evidence:** US stocks above $5, 1962-2014, LS, gross: 0.95% a month (Sharpe 0.17) against
  0.63% (0.12) for conventional momentum. A summary notes acceleration and deceleration are
  similar at 1-2-month holding periods. Exact regression form (normalisation of price, scaling of
  time) not stated in what I saw.
- **Fit:** a relative gate or tie-break. **Not shortlisted:** working paper only, gross,
  all-cap, unverified form, and the book's 1- and 3-month windows already reward recent
  strength.

#### C18. Moving-average distance (Avramov, Kaplanski & Subrahmanyam)

- **Source:** "Stock Return Predictability: New Evidence from Moving Averages of Prices and Firm
  Fundamentals", SSRN 3111334 (2018 version),
  https://anderson-review.ucla.edu/wp-content/uploads/2021/03/Avramov-Kaplanski-Subra_2018_SSRN-id3111334.pdf
  **[full text, working paper]**; published as "Moving average distance as a predictor of equity
  returns", *Review of Financial Economics* 39(2) (2021) **[abstract]**.
- **Rule:** MAD = MA(21) / MA(200), moving averages of split- and dividend-adjusted daily prices;
  robust to MA(250) and to short averages of 5-35 days. Deciles; next-month returns.
- **Evidence (US NYSE/AMEX/NASDAQ, price ≥ $5, June 1977-2018, LS):** next-month return rises to
  1.92% for the top decile; predictive power "goes well beyond momentum, the 52-week high,
  profitability"; in 2001-2015 momentum, the 52-week high and the trend factor "all disappear"
  (t = 0.70, −1.26, 0.45) while MAD stays significant (t = 2.80); "robust in the long-leg of the
  trade in recent years"; survives value weighting (VW alphas about 9% a year [secondary]) and
  reasonable costs.
- **Fit:** a relative buy gate (S7). It is related to, but not the same as, the 50-day EMA gate:
  the EMA gate is binary on one average; MAD ranks the distance between a fast and a slow average.
- **Failure modes:** all-cap sample; large-cap-only results not seen; MAD and the book's 6-12
  month windows overlap; published in a lower-tier journal.
- **Computable:** yes.

#### C19. Trend factor (Han, Zhou & Zhu 2016)

- **Source:** "A trend factor: Any economic gains from using information over investment
  horizons?", *JFE* 122(2), 352-375,
  https://econpapers.repec.org/RePEc:eee:jfinec:v:122:y:2016:i:2:p:352-375 **[abstract]**.
- **Rule [secondary]:** monthly cross-sectional regressions of returns on normalised moving
  averages of 3 to several hundred days; the forecast is the average of past coefficients times
  current averages. It is a **ranking**, and the MAD paper finds it insignificant in 2001-2015.
  **Not shortlisted.**

### 4.7 Horizon

#### C20. Intermediate-horizon momentum, the "echo" (Novy-Marx 2012; Goyal & Wahal 2015)

- **Sources:** Novy-Marx, R. (2012), "Is momentum really momentum?", *JFE* 103(3), 429-453,
  https://econpapers.repec.org/RePEc:eee:jfinec:v:103:y:2012:i:3:p:429-453 **[abstract]**:
  "Momentum is primarily driven by firms' performance 12 to seven months prior to portfolio
  formation"; recent (6-2) performance is "less profitable than" intermediate, especially among
  the largest, most liquid stocks. Goyal, A. & Wahal, S. (2015), "Is Momentum an Echo?", *JFQA*
  50(6), 1237-1267 **[abstract]**: a US echo exists, but "Any echo in the United States appears to
  be driven largely by a carryover of short-term reversals from month −2", and there is no robust
  echo in 37 other countries.
- **Fit:** a change of the score's horizon weights (S6). In the live score the 9- and 12-month
  windows carry 30% and are cumulative from today, so months 7-12 enter only diluted.
- **Failure modes:** contested; Goyal & Wahal's explanation (month −2 reversal) is weak in
  large caps (see C22), which, if anything, favours Novy-Marx for this universe; Paresh's lookback
  study found weight changes unreliable.
- **Computable:** yes.

#### C22. The skip month in large caps (Medhat & Schmeling 2022, as evidence)

- **Source:** Medhat, M. & Schmeling, M. (2022), "Short-term Momentum", *Review of Financial
  Studies* 35(3), 1480-1526; accepted version
  https://openaccess.city.ac.uk/id/eprint/31278/1/MS_short_term_mom_v27.pdf **[full text]**.
- **Evidence on the skip month:** among the **500 largest stocks**, the short-term reversal
  strategy within low-turnover stocks earns "just −2 basis points per month"; reversal is a
  microcap effect (−2.04% a month among microcaps, −0.74% among megacaps in the quintile sort).
- **Consequence:** the literature does **not** support adding a skip month to this book.
  Consistent with the rejected `str_drop10` (−5.3 pts a year). No test.

#### C23. Short-term momentum in high-turnover stocks (Medhat & Schmeling 2022)

- **Source:** as C22 **[full text]**.
- **Rule, as stated:** share turnover TO_1,0 = last month's trading volume / shares outstanding.
  Main test: conditional decile sorts on last month's return r_1,0 and then TO_1,0 (NYSE
  breakpoints), value-weighted, monthly. STMOM = winners minus losers within the highest-turnover
  decile: **+1.37% a month (t = 4.74)**, July 1963-December 2018. **Largest-500 version:**
  independent 2×2 sorts at the 250th rank on r_1,0 and on TO_1,0, value-weighted: STMOM (long
  high-return/high-turnover, short low-return/high-turnover) **0.42% a month, t = 4.91**. It
  persists for 12 months, is strongest among megacaps (0.53% a month, t = 2.53), survives
  conservative costs, and has been consistently positive except 1975-79.
- **Fit:** a buy gate (S4): do not buy a name in the low-return/high-turnover cell, which the
  paper finds keeps losing. It conditions the book's 1-month information on turnover instead of
  removing it.
- **Failure modes:** sample ends 2018; **turnover needs shares outstanding history, which the store
  does not have** (proxy below); a 2×2 median split is coarse; value-weighting in the paper,
  equal weight here.
- **Computable:** with a proxy only: shares_i = today's market cap / today's close (split-adjusted,
  constant through time). Buybacks and issuance make this wrong in early years (e.g. a company
  that has retired 40% of its shares since 2013 has its early turnover understated by about 40%).
  A median split across 500 names is partly robust to that, but the result is a lead, not a
  replication.

#### C24. Volume (Lee & Swaminathan 2000)

- *JF* 55(5), 2017-2069 **[abstract, from RESEARCH_FILTERS]**: low-volume winners continue
  longer. Needs turnover (proxy only, as C23); sample 1965-1995. **Not shortlisted**: C23 is the
  newer, large-cap-specific use of the same variable.

### 4.8 Portfolio construction

#### C21. Rebalance timing luck and tranching (Hoffstein, Faber & Braun 2020)

- **Source:** Hoffstein, C., Faber, N. & Braun, S. (2020), "Rebalance Timing Luck: The (Dumb)
  Luck of Smart Beta", https://new.epsilontheory.com/download/43455 **[full text]**; Newfound blog
  https://blog.thinknewfound.com/2019/11/the-dumb-timing-luck-of-smart-beta/ [secondary].
- **Rule:** build sub-indexes identical except for rebalance date; the "RTL-neutral" benchmark
  holds them in equal weight ("overlapping portfolios", "tranching"; Blitz et al. 2010, proved
  optimal by Hoffstein et al. 2019). RTL = annualised volatility of a sub-index's monthly returns
  minus the benchmark's. Analytic form L ≈ (T/f)·S/2 (turnover T, frequency f, long-short
  volatility of held vs not held S).
- **Evidence (US large caps 2000-2019, gross):** momentum (12-1) RTL, annual/semi-annual/quarterly
  rebalance: **50 stocks 7.44% / 5.92% / 4.16%**; 100 stocks 5.18% / 4.38% / 2.74%; 400 stocks
  1.03% / 0.88% / 0.74%. A replication of the S&P 500 Momentum index showed up to 4.5 pts of
  dispersion across schedules. RTL rises with concentration and turnover and falls with
  rebalance frequency.
- **Fit:** construction (S5): four tranches, offset by a week. Also used as **method**: every test
  in this document is run at four offsets (section 3.1).
- **Failure modes:** no expected gain in return; four trade dates a month; per-tranche costs if not
  netted.
- **Computable:** yes.

#### C25. Number of holdings and concentration

- **Sources:** Alpha Architect, "How many stocks should be in your portfolio?" (FactSet data
  1992-Mar 2025, hypothetical) [secondary]: fewer stocks raised factor returns; 50-100 suggested
  as the balance; the firm sells concentrated products. Hoffstein et al. (C21): concentration
  raises timing luck. No peer-reviewed large-cap long-only study of 20 vs 50 names was found.
- **Fit:** the owner's framework fixes 20 names. **Not shortlisted**; the four-offset protocol
  addresses the noise that concentration adds.

#### C26. Holding buffer (Novy-Marx & Velikov 2016)

- *RFS* 29(1) **[full text, per MOMENTUM_EVIDENCE]**: the buy/hold spread is "the most effective
  cost mitigation technique". The book already has it (buy in the top 20 qualified, keep in the
  top 40). Changing 40 is parameter tuning; **not shortlisted.**

#### C27. Rebalance frequency (Gray & Vogel's quarterly "smart" dates)

- From RESEARCH_FILTERS **[abstract/secondary]**: quarterly at the end of Feb/May/Aug/Nov, CAGR
  15.97% vs 15.06%, 1927-2014. Hoffstein et al. found no statistically significant schedule effect
  for momentum. The framework is monthly. **Not shortlisted.**

#### C28. Weighting: inverse volatility, score, equal

- **Sources:** du Plessis, J. & Hallerbach, W. (2017), "Volatility weighting applied to momentum
  strategies", *Journal of Alternative Investments* 19(3), 40-58 **[abstract]**: volatility
  weighting raises the Sharpe of momentum (US industry portfolios) through a timing and a
  stabilising effect. AQR's live funds weight by size and signal (Israel et al. 2021, per
  MOMENTUM_EVIDENCE).
- **Fit:** with 20 names and a 5% cap, any unequal weighting either breaches the cap or leaves
  cash. Feasible only with more names, which the framework fixes. Market-cap weighting needs
  historical caps (not in the store). **Not shortlisted.**

#### C29. Sector caps and neutrality

- See C13. The 40% cap stays as is.

### 4.9 Other recent (2018-2026) work seen

#### C30. Enhanced short-term signals (Blitz et al., Robeco 2022-2023)

- Robeco, "Beyond Fama-French: alpha from short-term signals" (2022) and the 2023 "Reversing the
  trend of short-term reversal" (Blitz, van der Grient, Honarvar) **[secondary, Robeco pages]**:
  short-term signals have gross alphas above 6% a year but net below −2% at 25 bps a trip;
  enhanced reversal needs short-term industry and factor momentum. High turnover; contradicts
  C22 for large caps. **Not shortlisted.**

No 2018-2026 SSRN paper was found that reports an out-of-sample improvement of **long-only US
large-cap** momentum specifically. The most recent directly relevant evidence is Medhat &
Schmeling (RFS 2022, largest-500 sorts to 2018), Cederburg et al. (JFE 2020) and Hanauer &
Windmüller (JBF 2023). Searches of SSRN pages themselves returned HTTP 403; the search was made
through search engines and the authors' or journals' pages.

---

## 5. Not testable with this data

| Idea | Source | Needs |
|---|---|---|
| Earnings momentum (SUE), earnings announcement returns | Chan, Jegadeesh & Lakonishok (1996, *JF* 51) [memory]; Novy-Marx (2015, NBER, "Fundamentally, momentum is fundamental momentum") [secondary] | EPS history, announcement dates |
| Analyst revisions | Chan et al. (1996) [memory] | analyst forecasts |
| AQR's 60/20/20 price/earnings/residual blend | Israel, Moskowitz, Ross & Serban (2021) [full text, per MOMENTUM_EVIDENCE] | earnings momentum (the residual part is S1) |
| Twin / fundamental momentum | Huang, Zhang, Zhou & Zhu [memory] | fundamentals |
| Fundamental anchoring (PDI) | Avramov et al. (C18) | quarterly accounting items |
| Overnight vs intraday momentum | Lou, Polk & Skouras (2019, *JFE*) [memory] | opening prices (the store has close, high, low, volume, no open) |
| IPCA momentum and reversal | Kelly, Moskowitz & Pruitt (2021, *JFE*) [memory] | firm characteristics |
| Size-conditioned momentum, value-weighting | many | historical market caps |
| Institutional ownership, short interest, news-based momentum | various | not in store |
| Exact turnover (C23, C24) | Medhat & Schmeling; Lee & Swaminathan | shares outstanding history (proxy only) |
| Moskowitz & Grinblatt's 20 industries | C12 | SIC codes |

A price-only "earnings-day" proxy (days of abnormal volume and a large move) is possible, but it
is our own construction and not any paper's rule; it is not proposed.

---

## 6. Ranking by strength of evidence for US large-cap long-only use

Grades: **A** = peer-reviewed, several independent studies, large-cap or long-side evidence, and
out-of-sample survival. **B** = peer-reviewed and large-cap evidence, but long-short only or a
single study. **C** = one study, all-cap or working paper. **D** = contradicted, already tested, or
not applicable to a 20-stock long-only book.

| Rank | Candidate | Grade | Why |
|---|---|---|---|
| 1 | C01-C03 Residual momentum, FF3/36m/12-2 standardised | **B+** | Peer-reviewed, replicated (BHV, H&W, international), large-cap LS Sharpe 0.36→0.60; AQR uses it live (20%). Against: winner-decile return lower (18.4 vs 21.3%), Sharpe gain on the long side small (0.73→0.75); weakened after the early 2000s (BHV, secondary). |
| 2 | C05/C08 Constant-volatility scaling | **B** | The one improvement that survives Cederburg's out-of-sample critique, for all nine momentum strategies. Against: LS only; crashes come from the short side; Barroso & Detzel: zero after costs for non-market factors. |
| 3 | C23 Short-term momentum (high turnover) | **B** | RFS 2022, strongest in the largest 500 (t = 4.91), survives costs. Against: one study, ends 2018, turnover proxy only. |
| 4 | C21 Tranching | **B** (for what it claims) | Not a return claim; strong evidence that a single schedule is noisy for concentrated momentum. |
| 5 | C06 Dynamic momentum | **B−** | JFE, 4 markets and 5 asset classes. Against: in-sample parameters, mechanism is about losers. |
| 6 | C18 MAD | **C+** | Survives 2001-2015 when momentum does not; long leg robust; VW. Against: all-cap, lower-tier journal, overlaps EMA gate. |
| 7 | C20 Intermediate horizon (12-7) | **C** | JFE, says strongest in large caps; contested by Goyal & Wahal (US echo = month-2 reversal carryover; no echo abroad). |
| 8 | C17 Acceleration | C− | Working paper, gross, all-cap. |
| 9 | C11 Factor momentum | C− (for this use) | Strong for factors; no stock-level rule. |
| 10 | C07 Moreira-Muir | (in 2) | Same family as C05, noisier window. |
| 11 | C24 Volume | C− | Older sample; proxy. |
| 12 | C12 Industry momentum | B for LS; here D as a new test | Already tested; enters C2 only. |
| 13 | C19 Trend factor | D | A ranking; insignificant 2001-2015. |
| 14 | C10 Turning points | D here | Market gate; gates rejected on return. |
| 15 | C09 TS/dual momentum | D | Tested; edge is net exposure. |
| 16 | C13 Sector neutrality | D | Degrades long-only and momentum (EHL 2023). |
| 17 | C16 IVOL filter | D | Momentum stronger in high IVOL; vol gate rejected. |
| 18 | C14/C15 FIP, consistency | D (as new) | Tested; awaiting point-in-time rerun. |
| 19 | C22 Skip month | evidence against adding one | Large-cap reversal ≈ 0. |
| 20 | C25-C29 Concentration, buffer, frequency, weighting, sector caps | D | Fixed by the framework, infeasible under the cap, or parameter tuning. |
| 21 | C30 Short-term signals | D | Net negative after costs. |

---

## 7. Shortlist and combinations

Seven tests and two combinations. Everything not listed here is out. Each specification below is
complete; where it says "as base" the base book's rule is unchanged.

Notation: m = the month whose last session (shifted by the offset in 3.1) is the signal date;
"month t" in a paper corresponds to month m+1 (the holding month). French data are used through
month m−1 only (section 2).

### S1. Residual momentum blended into the score (C01-C03)

- **Monthly stock returns:** r_i,k = close at the last session of month k / close at the last
  session of month k−1 − 1, adjusted closes. Excess return: minus French RF_k.
- **Betas:** for each stock that is an S&P 500 member at the signal date, OLS of excess returns on
  Mkt-RF, SMB, HML (French monthly) over the **36 months m−36 … m−1**, with an intercept.
  (The paper uses t−36 … t−1 = m−35 … m; shifted by one month for the publication lag. Our choice.)
  Require all 36 monthly returns; otherwise the stock's residual score is set to 0 after
  standardisation (neutral). (The paper excludes such stocks; our choice, so the universe is the
  same as the base.)
- **Residuals:** e_i,k = r_i,k − RF_k − (β1 MktRF_k + β2 SMB_k + β3 HML_k), **intercept excluded**,
  for the 11 months k = m−11 … m−1 (the paper's t−12 … t−2; here the skip of the paper's month
  t−1 = m is forced by the lag, so the paper's skip is kept exactly).
- **Residual score:** RES_i = Σ_{k=m−11}^{m−1} e_i,k / sqrt( Σ_{k=m−11}^{m−1} (e_i,k − ē_i)² ),
  ē_i = mean of those 11 residuals (Hanauer & Windmüller eq. 9).
- **Blend:** z(·) = cross-sectional z-score over the day's members, winsorised the same way as the
  live score's components. New score = **0.75 × z(base score) + 0.25 × z(RES)**. The 3:1 ratio
  is AQR's live funds' price:residual ratio (60:20). Everything after the score (filters, top
  20, keep top 40, caps) as base.
- **Fallback if the owner rules out score changes:** buy gate, the worse half of the qualified
  not-held names by RES are not bought (`research_drop` 0.5, `research_gate_on` "buy"). Run one or
  the other, decided by the owner before the run.
- **Expected:** lower volatility and tracking error; return gain uncertain (winner-decile return
  was lower in the paper).

### S2. Momentum-volatility scaling of the active bet (C05, C08)

- **Signal:** French daily UMD returns u_d. σ̂_m = sqrt( 252 × (1/126) × Σ u_d² ), over the 126
  sessions ending at the last session of month **m−1** (lag rule). This is Barroso &
  Santa-Clara's realised variance, annualised.
- **Weight on the momentum book:** w_m = min(1, 0.12 / σ̂_m). 12% is the paper's target. Cap 1:
  no leverage.
- **Remainder:** 1 − w_m in SPY (total return). The book itself is built exactly as base at full
  size and then scaled by w_m.
- **Trades and costs:** at each fill the split between book and SPY is reset; cost 10 bps round
  trip on |w_m − w_{m−1}| plus the book's own trades scaled by w_m.
- **Reported robustness (not a separate verdict):** the same with downside variance (only u_d < 0
  in the sum, × 2) per Wang & Yan.

### S3. Daniel-Moskowitz dynamic weight on the active bet, parameters frozen (C06)

- **Estimation (once, before the test, on French data January 1927 to December 2007):**
  - I_B,k = 1 if the cumulative market return (Mkt-RF + RF, compounded) over months k−23 … k is
    negative.
  - σ²_mkt,k = variance of daily Mkt-RF over the 126 sessions ending at the end of month k.
  - Regress monthly UMD_{k+1} on a constant and I_B,k × σ²_mkt,k (OLS): UMD_{k+1} = γ0 + γ1 I_B,k σ²_mkt,k + e.
  - σ²_UMD,k = realised variance of daily UMD over the 126 sessions ending at month k, in monthly
    units (× 21). (The paper adds a GJR-GARCH forecast; dropped here, our choice, to avoid fitting
    a GARCH.)
  - raw_k = (γ0 + γ1 I_B,k σ²_mkt,k) / σ²_UMD,k; κ = 1 / median(raw_k) over 1927-2007.
  - Write γ0, γ1, κ into the results before the first test run.
- **Application:** at signal month m, using French data through m−1 (I_B and the variances
  computed with k = m−1): w_m = min(1, max(0, κ × raw_{m−1})). Remainder in SPY, costs as S2.
- **Expected:** w = 1 most months, cut only in volatile bear states.

### S4. Short-term momentum buy gate (C23)

- **Turnover proxy:** shares_i = market cap today / adjusted close today. TO_i,m = Σ volume over the
  sessions of month m / shares_i.
- **Sort:** among the day's S&P 500 members, independently rank on r_i,m (month m's return) and
  on TO_i,m; split each at the median (the paper's largest-500 2×2 at the 250th rank).
- **Gate:** a not-held name in the **low-return, high-turnover** cell may not be bought
  (`research_gate_on` "buy"). Holdings unaffected.
- **Before running:** check the proxy on two names with large buybacks and two with large issuance;
  report how often the cell assignment would change if shares were 30% higher in 2011.

### S5. Four tranches (C21)

- Capital split into four equal sub-books. Sub-book j (j = 0, 1, 2, 3) runs the full base rules
  with its signal 5j sessions before each month's last session, filled at the next close.
- Caps (5% a stock, 40% a sector) applied within each sub-book, so the total respects them.
- Costs charged per sub-book on its own trades (conservative; no netting).
- No rebalancing between sub-books.
- Primary metric: CAGR dispersion across the four single-schedule base runs against the
  tranched book's return (section 3.3); return and drawdown reported.

### S6. Intermediate horizon (C20)

- Replace the 9-month (20%) and 12-month (10%) windows with one window of 30%: the vol-adjusted
  return over **months m−11 … m−6** (close at the end of month m−12 to close at the end of month
  m−6; the paper's t−12 … t−7). Other windows unchanged: 1M 10%, 3M 30%, 6M 30%, 12-7 30%.
- Winsorisation and z-scoring as the live score.

### S7. Moving-average distance buy gate (C18)

- MAD_i = mean of the last 21 adjusted closes / mean of the last 200 adjusted closes, at the
  signal session. Require 200 sessions of history; otherwise the name passes.
- Relative buy gate: of the qualified not-held names, the 20% with the lowest MAD are not bought
  (`research_values` = MAD, `research_drop` 0.2, `research_gate_on` "buy"). 20% is one round
  value (the paper uses deciles; our choice, matching the earlier drop-20 tests).

### Combinations (pre-specified, at most two)

- **C1 = S1 + S2:** the residual-blended score book, scaled by S2's weight with the remainder in
  SPY. Why: Hanauer & Windmüller (2019 WP) find the volatility-scaling alpha "distinctive from the
  idiosyncratic momentum alpha", so the two should add. Judged as an overlay (Sharpe), against
  the base and against S1 alone.
- **C2 = S1 + the 12-month sector-momentum buy gate** exactly as `industry_top` in
  RESEARCH_FILTERS (only names whose GICS sector is in the stronger half of the 11 by equal-weight
  12-month return). Why: residual momentum removes factor bets within the stock ranking; sector
  momentum is the across-sector component that Ehsani, Harvey & Li show should be kept in a
  long-only book; and it is the one prior pass. Judged on CAGR.

### Why this shortlist

- It takes the two families with the best out-of-sample evidence for momentum specifically
  (residual momentum; volatility management) and tests them in the form the papers use (three
  factors, 36 months; the factor's own volatility), not the simplified forms already tested.
- It adds one large-cap-specific recent result (short-term momentum, RFS 2022) that conditions
  the 1-month information the book already uses instead of removing it.
- It treats timing luck as both a candidate and a method, because a 20-stock monthly book's
  backtest differences of 1-3 pts a year are within its likely timing-luck range.
- MAD and the 12-7 horizon are the two price-only signals with peer-reviewed evidence that
  survived 2001-2015 (MAD) or that the source says is strongest among the largest stocks (12-7).
- Left out deliberately: anything already tested in substance, anything the literature says hurts
  long-only momentum (sector neutrality, IVOL filters, skip month), working papers alone
  (acceleration), and construction changes the framework fixes (number of names, weighting).

---

## 8. What was not checked

- **Read in full in this session:** Blitz, Huij & Martens (accepted manuscript); Daniel &
  Moskowitz (NBER WP 20439, not the JFE version); Moreira & Muir (published); Cederburg et al.
  (published); Ehsani & Linnainmaa (NBER WP 25551, not the JF version); Hanauer & Windmüller
  (2019 WP, not the JBF version, whose abstract differs); Hoffstein, Faber & Braun (2020);
  Medhat & Schmeling (accepted version); Avramov, Kaplanski & Subrahmanyam (2018 SSRN version,
  not the RFE version); Ehsani, Harvey & Li (FAJ 2023).
- **Abstract or secondary only:** Barroso & Santa-Clara (formula from a citing paper), Blitz,
  Hanauer & Vidojevic, Barroso & Detzel, Wang & Yan, DeMiguel et al., Moskowitz & Grinblatt,
  Novy-Marx, Goyal & Wahal, Lim, Wang & Yao, Goulding et al., Chen, Yu & Wang, Han, Zhou & Zhu,
  Grinblatt & Moskowitz, Arena et al., Chaves, Gutierrez & Pirinsky, du Plessis & Hallerbach,
  Alpha Architect's concentration study, Robeco's short-term-signal pages.
- **From memory:** Ang et al. (2006) IVOL definition; Grinblatt & Moskowitz's 8-of-12 rule; Lou,
  Polk & Skouras; Kelly, Moskowitz & Pruitt; Chan, Jegadeesh & Lakonishok; Huang et al. twin
  momentum.
- **SSRN** returned HTTP 403 to direct fetches; no SSRN PDF was read.
- **Not established:** any published test of these ideas in a 20-stock, equal-weight, long-only
  S&P 500 book; large-cap-only results for MAD and acceleration; momentum-specific after-cost
  results for volatility management (Barroso & Detzel); whether the store's volume is
  split-adjusted (check in section 2); whether SPY total-return prices are in the store.
- **Departures from the papers, all fixed above:** the one-month French publication lag (S1-S3);
  neutral residual score for short histories (S1); realised-variance-only volatility forecast and
  frozen 1927-2007 parameters (S3); no leverage and SPY instead of a short leg (S2, S3); turnover
  proxy from today's shares (S4); a 20% drop instead of deciles (S7); median splits on S&P 500
  members instead of the paper's 500 largest (S4).


---

## Results (10 Nov 2026)

### Fixed before the first run

Written here before any backtest of this study was run (scripts/research_prereg.py).

- **S3 parameters** (French data, vintage 202609, downloaded 10 Nov 2026; regression on months
  k = Jun 1928 to Nov 2007, 954 months, the first k with 24 months of market returns and 126 daily
  sessions of UMD): **γ0 = 0.008863, γ1 = −35.207, κ = 0.054452** (κ = 1/median(raw_k) over 955
  months; by construction w < 1 in half of the months of 1927-2007).
- **Interpretation choices** (the spec left these open; each is the reading closest to the paper
  that the book's mechanics allow):
  - Base keywords: live_kwargs() (TRACK_RECORD_CONFIG) with members_only_scoring_from, ema_warmup_from, hold_cap, hold_cap_from, buy_size and weight_reset_months set to None (all forward-dated to the 30 Nov 2026 signal, so off in the sample either way). The composite is therefore z-scored over every column with a price (all ever-members loaded), as the record does before 30 Nov 2026; membership restricts who may be held.
  - Offsets: the signal is the session 0/5/10/15 sessions before each calendar month's last session (run_backtest signal_offset). 'Month m' is the calendar month holding the signal.
  - Common start: m0 = the first month at which S1 has 36 monthly returns ending m-1 (and the membership covers the signal). Every run starts with its own offset's signal in m0; all are evaluated on the sessions after the offset-0 fill of m0 (the latest first fill) to the last session of the last complete month.
  - Secondary sample: the same runs, sessions from 1 Jan 2020 (state carried from 2011, not a fresh start).
  - S1: monthly returns are calendar month-end to month-end at every offset (they must line up with French's months); RES is computed over every stock, then z-scored over the day's members; RES of a member without 36 returns is 0 after standardisation. z(base) is the winsorised z of the composite over the day's members with a score.
  - S4 and S6 under an offset: 'the end of month k' is the session the offset shifts it to (offset o: o sessions before month k's last session), so each offset is a pure time shift. S4's month-m return is the close at the signal over the close at the previous shifted month end; its volume is summed over the sessions after that to the signal. S6's 12-7 window runs from the shifted end of m-12 to the shifted end of m-6; its opening and closing prices use the 5-session stale-anchor rule.
  - S4: shares = market cap in data/market_caps.csv / the store's adjusted close on that file's AsOf date; a member with no market cap (most former members) has no turnover, is left out of the sort and passes. Median splits: low return = below the members' median, high turnover = above it.
  - S7 and the S1-fallback wording: the engine keywords named by the spec are used (research_drop over all the qualified, held names exempt), not a recount over the not-held names only. A name with fewer than 200 closes passes (MAD set to +inf).
  - S2: sigma over the 126 French daily UMD sessions ending at the last session of month m-1, sqrt(252 * mean(u^2)). Downside robustness: mean over the same 126 of u^2 for u<0 only, times 2.
  - S3: I_B from compounded monthly Mkt-RF+RF over k-23..k; sigma^2_mkt = sample variance (ddof 1) of daily Mkt-RF over the 126 sessions to the end of month k; sigma^2_UMD = 21 * mean(u^2) over the same window; regression on k = Jan 1927 .. Nov 2007 (UMD_{k+1} up to Dec 2007), kappa = 1/median(raw_k) over k in 1927-2007 with all inputs.
  - Overlays: at each fill the split is reset to w; cost = cost_bps x |w_m - w_{m-1}| on the first session after the fill, plus the book's own (full-size) costs scaled by w; the first fill pays cost_bps/2 on the SPY sleeve's (1-w_0), as the engine charges half a round trip to establish a book. Turnover: w x book turnover + |dw| (one way).
  - S5: sub-book j is the base run at offset 5j, each worth a quarter at the common start, never rebalanced. Its own four-offset dispersion is zero by construction (it holds all four schedules), so the 'dispersion falls by a third' test is met mechanically and the verdict rests on the CAGR test; dispersion = sample standard deviation (ddof 1) of the four base CAGRs. Hoffstein's RTL (tracking error of each single schedule against the tranched book) is reported beside it. S5 not passing is 'reject' if its CAGR shortfall exceeds 0.5 pt in both halves, else 'inconclusive'.
  - Statistics: CAGR = compound daily growth to the power 252/sessions; Sharpe = mean(r - RF)/sd(r - RF) * sqrt(252) with French daily RF (sessions after French's last day use its last RF); TE and IR against SPY_TR (data/benchmarks.csv); turnover a year = one-way turnover % of the fills in the sample / years. Variant-minus-base gaps are means over the four offsets; the bootstrap applies one set of block indices to every series and RF.
  - Verdict (3.3) on each sample: pass = primary gap > 0 in both halves of that sample, ahead in >= 90% of draws, gap > 0 at all four offsets and > 0 at 20 bps, mean max-drawdown gap >= -2 pts, mean turnover gap <= +15 pts a year. Reject = behind in both halves or ahead in <= 20% of draws. Else inconclusive.

### Data basis (section 2 checks, run 10 Nov 2026 before the backtests)

- **Final basis: the price store alone** (`data/prices` after the owner's import of the
  Johnbrick123 former-member rows, commit a4ef295), no `--extra-prices`. 825 symbols loaded.
- **Volume is split-adjusted** (store): median volume over the 20 sessions after / before the split
  was 0.57 for AAPL 9 Jun 2014 (7:1), 1.01 for AAPL 31 Aug 2020 (4:1) and 0.69 for NVDA 10 Jun 2024
  (10:1); an unadjusted series would jump by the split ratio. AAPL's pre-2014 volume (about 300M a
  day) is in post-split shares.
- **Prices start 2 Jan 2008**, so the first monthly return is February 2008 (confirmed); S1 is first
  computable at the end of February 2011 (m0 = 2011-02). m0's signal fills on 1 Mar 2011 at offset 0
  and in February at offsets 5/10/15. **Primary sample: the sessions after 1 Mar 2011 to 30 Oct 2026**
  (3,941 sessions; 30 Oct 2026 is the last session of October, the last complete month on the day of
  the run; fixed). **Secondary: 2 Jan 2020 to 30 Oct 2026** (1,717 sessions).
- **Membership:** `index_history('sp500')`, **baseline 31 Dec 2009**, 165 changes after it, so every
  signal in the sample is point in time. 856 ever-members, 353 of them former members.
- **Coverage:** of the 94,912 point-in-time member-months at the offset-0 signals (Feb 2011 to Oct 2026),
  **93,971 = 99.0% have a price** (a close in the month's last 6 sessions); 98.5-99.9% every year
  except 2024 (96.7%) and 2025 (97.9%). The 941 without are mostly reused or later tickers in the store
  (FOXA 97 member-months: the 2013-2019 Twenty-First Century Fox; DOW 80: Dow Chemical before 2017; IR,
  HWM, SNDK, FOX, WBD, KVUE) and EA and AVB, which have store prices only to 10 Oct 2023 although the
  timeline lists them as members after that (a lead for the data work; not checked further). The 31
  ever-member symbols with no price at all are almost all old tickers of renamed companies (FB, ANTM,
  UTX, ...) that the timeline maps to today's symbol.
- **Sectors:** the record's map (`record_sector_map`): today's labels, so a past sector is today's
  sector. 135 symbols (mostly the imported former members) have none and are capped together as
  "Other" under the 40% sector cap.
- **French data:** `F-F_Research_Data_Factors`, its daily file, `F-F_Momentum_Factor` and its daily
  file, all **CRSP vintage 202609** (files dated 26 Oct 2026), downloaded 10 Nov 2026 from Kenneth
  French's site and frozen in the session's scratchpad (`french/`); data through 30 Sep 2026. The m-1
  lag rule is applied in S1-S3 and C1. `data/french_umd.csv` was not used.
- **S4 proxy check:** shares = market cap / adjusted close of 9 Nov 2026. If one member's shares had
  been 30% higher in 2011, its cell would change in 7.7% of 2011 member-months (318 of 4,109). On
  average 342 of about 500 members a month were sortable in 2011 (former members have no market cap,
  so they are left out of the sort and pass the gate). **Not checked:** dated share counts for two
  buyback and two issuance names; the store has no share history, so the proxy is unverified.

### Results

Every figure is the mean over the four offsets (0, 5, 10, 15 sessions before the month end) of the
variant minus the base on the same sessions, at 10 bps unless marked. The bootstrap is 2,000 paired
63-session block draws, seed 20261110. CAGR gaps are in points and Sharpe gaps in Sharpe units. The
run outputs (the daily returns of all 48 backtests, report.md and results.json) are in the session
scratchpad under `prereg_runs/store_v2`.

#### Primary sample, store (99.0% coverage) (2011-03-02 to 2026-10-30, halves split 2018-12-28)

Base (mean of 4 offsets, 10 bps): CAGR 13.52%, max DD -33.8%, Sharpe 0.70, vol 18.3%, turnover 499%/yr, TE 12.8%, IR -0.01; by offset 0/5/10/15 CAGR 14.0% / 14.0% / 12.6% / 13.4%, max DD -27.8% / -33.6% / -40.9% / -32.9%, Sharpe 0.73 / 0.73 / 0.65 / 0.69.

| | Metric | CAGR | Max DD | Sharpe | Turn./yr | Primary gap (90% range) | Ahead in | H1 / H2 | By offset 0/5/10/15 | Gap at 20 bps | ΔMDD | ΔTurn. | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | CAGR | 14.13% | -35.0% | 0.71 | 444 | +0.61 (-0.65 to +1.95) | 77.7% | +0.11 / +1.14 | +0.85 / -0.79 / +1.52 / +0.88 | +0.67 | -1.20 | -56 | **inconclusive** |
| S2 | Sharpe | 14.22% | -33.2% | 0.77 | 454 | +0.068 (+0.002 to +0.146) | 95.4% | +0.010 / +0.104 | +0.057 / +0.046 / +0.095 / +0.076 | +0.069 | +0.57 | -46 | **pass** |
| S3 | Sharpe | 14.61% | -33.5% | 0.81 | 276 | +0.106 (-0.069 to +0.294) | 83.5% | +0.036 / +0.148 | +0.084 / +0.079 / +0.150 / +0.111 | +0.117 | +0.30 | -223 | **inconclusive** |
| S4 | CAGR | 13.52% | -33.8% | 0.70 | 497 | -0.00 (-0.18 to +0.16) | 46.9% | -0.01 / +0.00 | +0.12 / -0.09 / +0.07 / -0.11 | +0.00 | +0.02 | -2 | **inconclusive** |
| S5 | CAGR dispersion | 13.54% | -33.7% | 0.71 | 499 | base sd 0.66 pt vs 0 (by construction); CAGR vs mean base +0.02 | — | +0.02 / +0.00 | RTL 3.76 pt | +0.02 | +0.11 | +0 | pass |
| S6 | CAGR | 12.12% | -33.6% | 0.63 | 531 | -1.40 (-3.38 to -0.04) | 4.8% | -2.00 / -0.77 | -0.75 / -2.85 / -0.19 / -1.82 | -1.43 | +0.17 | +31 | **reject** |
| S7 | CAGR | 13.53% | -33.1% | 0.70 | 498 | +0.01 (-0.11 to +0.09) | 42.7% | -0.04 / +0.06 | +0.15 / -0.18 / -0.13 / +0.20 | +0.01 | +0.66 | -1 | **inconclusive** |
| C1 | Sharpe | 14.72% | -34.6% | 0.78 | 405 | +0.077 (-0.015 to +0.176) | 92.0% | +0.009 / +0.123 | +0.076 / -0.003 / +0.135 / +0.099 | +0.081 | -0.79 | -95 | **inconclusive** |
| C2 | CAGR | 12.84% | -34.2% | 0.64 | 425 | -0.68 (-2.44 to +1.05) | 23.7% | -1.09 / -0.26 | -0.75 / -1.65 / -0.34 / +0.01 | -0.59 | -0.37 | -74 | **reject** |

C1 against S1 alone: Sharpe gap +0.066 (+0.002 to +0.145), ahead in 95.2%, halves +0.007 / +0.099. S2 downside-variance robustness: Sharpe gap +0.069, ahead in 94.2%.

#### Secondary sample, store (99.0% coverage) (2020-01-02 to 2026-10-30, halves split 2023-05-31)

Base (mean of 4 offsets, 10 bps): CAGR 15.21%, max DD -33.1%, Sharpe 0.62, vol 21.9%, turnover 516%/yr, TE 16.6%, IR 0.04; by offset 0/5/10/15 CAGR 17.5% / 16.6% / 11.4% / 15.4%, max DD -26.5% / -33.1% / -40.9% / -31.9%, Sharpe 0.72 / 0.68 / 0.47 / 0.62.

| | Metric | CAGR | Max DD | Sharpe | Turn./yr | Primary gap (90% range) | Ahead in | H1 / H2 | By offset 0/5/10/15 | Gap at 20 bps | ΔMDD | ΔTurn. | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | CAGR | 16.59% | -34.7% | 0.66 | 464 | +1.38 (-1.16 to +3.46) | 77.2% | -0.75 / +3.93 | +1.93 / -1.55 / +3.63 / +1.53 | +1.44 | -1.58 | -53 | **inconclusive** |
| S2 | Sharpe | 16.42% | -33.1% | 0.72 | 419 | +0.095 (-0.017 to +0.258) | 92.2% | +0.124 / +0.083 | +0.075 / +0.059 / +0.142 / +0.102 | +0.097 | -0.04 | -97 | **pass** |
| S3 | Sharpe | 15.97% | -33.5% | 0.72 | 151 | +0.096 (-0.192 to +0.459) | 74.5% | +0.157 / +0.154 | +0.024 / +0.045 / +0.216 / +0.100 | +0.112 | -0.40 | -366 | **inconclusive** |
| S4 | CAGR | 15.28% | -33.1% | 0.63 | 514 | +0.07 (-0.21 to +0.26) | 64.0% | +0.01 / +0.15 | +0.08 / -0.21 / -0.02 / +0.44 | +0.07 | +0.01 | -2 | **inconclusive** |
| S5 | CAGR dispersion | 15.20% | -33.3% | 0.63 | 516 | base sd 2.67 pt vs 0 (by construction); CAGR vs mean base -0.01 | — | -0.04 / -0.05 | RTL 4.77 pt | -0.01 | -0.21 | -0 | pass |
| S6 | CAGR | 14.35% | -33.6% | 0.58 | 541 | -0.86 (-5.08 to +1.26) | 17.1% | -1.97 / +0.46 | +1.26 / -4.40 / +1.17 / -1.47 | -0.88 | -0.53 | +24 | **reject** |
| S7 | CAGR | 15.29% | -32.4% | 0.63 | 515 | +0.08 (-0.17 to +0.19) | 55.4% | -0.08 / +0.28 | +0.35 / -0.41 / -0.23 / +0.61 | +0.08 | +0.67 | -2 | **inconclusive** |
| C1 | Sharpe | 17.59% | -34.5% | 0.75 | 379 | +0.122 (-0.024 to +0.283) | 91.4% | +0.104 / +0.158 | +0.124 / -0.013 / +0.240 / +0.137 | +0.127 | -1.39 | -137 | **inconclusive** |
| C2 | CAGR | 15.00% | -33.9% | 0.59 | 451 | -0.21 (-3.78 to +2.68) | 33.4% | -2.98 / +3.10 | -0.03 / -3.73 / +1.54 / +1.36 | -0.14 | -0.84 | -65 | **inconclusive** |

C1 against S1 alone: Sharpe gap +0.089 (-0.010 to +0.251), ahead in 92.7%, halves +0.133 / +0.063. S2 downside-variance robustness: Sharpe gap +0.097, ahead in 91.2%.

### Verdicts (store, 99.0% coverage)

| | Primary 2011-2026 | Secondary 2020-2026 |
|---|---|---|
| S1 residual blend | inconclusive | inconclusive |
| S2 UMD-volatility scaling | **pass** | **pass** |
| S3 Daniel-Moskowitz dynamic weight | inconclusive | inconclusive |
| S4 short-term-momentum gate | inconclusive | inconclusive |
| S5 four tranches | pass (mechanical: see below) | pass (mechanical) |
| S6 12-7 horizon | **reject** | **reject** |
| S7 MAD gate | inconclusive | inconclusive |
| C1 = S1 + S2 | inconclusive (offset 5 at -0.003) | inconclusive (offset 5 at -0.013) |
| C2 = S1 + sector gate | **reject** | inconclusive |

What the verdicts mean:

- **S2 passes every rule in both samples, but narrowly, and part of the gain is mechanical.**
  - Primary: Sharpe +0.068 (90% range +0.002 to +0.146), ahead in 95.4% of draws, ahead at all four
    offsets and at 20 bps. The first half is barely ahead (+0.010). Max drawdown is not lower
    (+0.6 pt, within the 2-pt rule). The sleeve's mean weight is 0.84.
  - Part of the gain comes simply from holding SPY beside the book. A **post-hoc diagnostic** (not a
    pre-registered test, and not a verdict): a constant 84% book / 16% SPY split with the same costs
    gains +0.032 Sharpe in the primary sample and +0.028 in 2020+. That is about half of S2's +0.068
    and +0.095, so the timing part is about +0.04 Sharpe.
  - Per 3.3, S2 is a candidate for a forward shadow; that is the owner's decision.
- **C1** is ahead on Sharpe (+0.077, 92.0% of draws) but behind at offset 5 (-0.003), so it does not
  pass. Against S1 alone it is ahead (+0.066, 95.2%). Its gain comes from S2's overlay, not from S1.
- **S1:**
  - Ahead on CAGR: +0.61 pt in the primary sample, +1.38 pt in 2020+.
  - Turnover is lower by 56 pts a year, but max drawdown is 1.2 pts worse.
  - Ahead in only 78% of draws and behind at offset 5, so inconclusive.
- **S3** raises Sharpe (+0.106) mostly by holding SPY. Its weight averaged 0.44 (below 1 at 90% of
  fills, and down to 0), not the "w = 1 most months" the spec expected. The reason: UMD's 2011-2026
  volatility is above its 1927-2007 median, and κ sets that median to 1. Tracking error falls to 5%.
  Ahead in 83.5% of draws: inconclusive.
- **S5 meets both written tests, but the first is met by construction.** The tranched book holds all
  four schedules, so its four-offset dispersion is zero.
  - Its CAGR is within 0.5 pt of the base's mean (+0.02 pt; 2020+ -0.01).
  - What it removes is timing luck. The four base schedules span 1.4 pts of CAGR in the primary sample
    (sd 0.66 pt) and 6.1 pts in 2020+ (sd 2.67 pt). Offset 10 had a -40.9% drawdown against -27.8% at
    offset 0.
  - Hoffstein's RTL (one schedule's tracking error against the tranches) is 3.8 pts a year (4.8 in
    2020+).
  - The verdict says tranching costs nothing in return; it does not say it adds any.
- **S6 is rejected in both samples:** -1.40 pt a year, both halves behind, ahead in 4.8% of draws,
  turnover +31 pts.
- **C2 is rejected on the primary sample** (-0.68 pt, both halves behind, 23.7% of draws) and is
  inconclusive in 2020+. The sector gate that passed on today's S&P 1500 list does not add to S1 on
  point-in-time S&P 500 data.
- **S4 and S7** are within 0.1 pt of the base, with no consistent sign.

### Sensitivity to the price basis (reported, not a verdict)

The same 48 runs were also made on two earlier states of the data on 10 Nov 2026. Both ran before the
import, with the same code and specifications:

| Basis | Coverage | Base CAGR / MDD / Sharpe (primary) | Verdicts that differ from the final basis |
|---|---|---|---|
| Store before the import | 91.4% (76% in 2011, rising to 97% in 2019) | 14.07% / -33.2% / 0.72 | S4 **reject** primary (-0.15 pt, 5% of draws); C1 inconclusive (89.5%); others the same |
| Store before the import + research-only file (146 symbols added) | 98.6% | 13.49% / -33.5% / 0.70 | C1 **pass** primary (92.0%, offset 5 +0.017); others the same |

The research-file run and the final store run should be equivalent. Every CAGR differs by at most
0.24 pt (C2, primary) and every Sharpe by at most 0.009. These differences are the store's versions of
the imported rows plus 7 symbols that were already in the store, against the file's. They flip one
borderline verdict: C1's offset-5 gap, +0.017 against -0.003. With 91% coverage the base looks
0.5 pt a year better, which is the survivorship the import removed.

### Bug fixes and deviations

- **Spec:** no bug fix to the written spec was needed after a run. No specification was changed and
  no neighbour was added.
- **Harness changes made while the first runs were going.** Neither touched a reported number:
  - S1's residual regression no longer requires three stocks in the cross-section. A two-stock
    synthetic test failed; real runs have hundreds.
  - The overlay's cost is now taken from the account pro rata. Overlays are computed only in
    `report`, which ran after the change.
- **S5's dispersion test is degenerate as written** (see above). Reported, not changed.
- **Readings already listed under "Fixed before the first run":**
  - S1's z(base) is taken over the members, while the composite is taken over every priced column.
  - S4 and S6 use offset-shifted month ends; S1 uses calendar month ends.
  - S7 uses the engine's drop over all the qualified names.
- **Found in passing, not part of this study:** `scripts/research_filters.py` trims prices to the end
  of the last complete month, and `completed_month_window` then treats that month as still in
  progress. Its runs therefore end a month earlier than its report's label says. Not fixed here.

### What was not checked

- Share counts behind S4's turnover proxy: there is no share history, and turnover uses today's
  shares.
- The imported former-member prices against a second source in this study (the data session checked
  them; docs/DATA_CORRECTNESS.md). They carry no GICS sector.
- Why EA and AVB stop in the store in October 2023, and the other gaps above.
- The 1.0% of member-months without a price (remaining survivorship).
- French's later revisions: the 202609 files are frozen, and a later vintage may differ.
- **Live use:** French published September 2026 on 26 Oct 2026. In real time, an end-of-October signal
  could not always have used month m-1, so a live S2 needs the spec's "latest published month"
  fallback. The backtest assumes m-1 was available.
- **Scope:** this pre-registration had no walk-forward, and none was run.
