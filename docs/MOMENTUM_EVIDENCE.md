# Momentum returns: what the recent evidence says

Prepared 10 Nov 2026 for a long-only, 20-stock, monthly-rebalanced S&P 500 momentum strategy.

How to read the tags:
- **LS / LO**: long-short or long-only.
- **gross / net**: before or after trading costs (and fees, for funds).
- **[computed]**: I calculated the figure from the named public data file. The script is in the scratchpad (`umd_stats.py`, `lo_stats.py`).
- **[full text]**: I read the figure in the paper's own text (PDF converted to text).
- **[abstract]**: I saw only the abstract or the publisher's listing.
- **[secondary]**: I saw it only in a summary by someone else. **Not verified.**

---

## Summary

- **Long-short US momentum has been much weaker since 2000.**
  - Kenneth French's UMD factor (LS, gross, 1927-2026) [computed]:

    | Period | Mean per year | t-stat | Sharpe |
    |---|---|---|---|
    | 1927-1999 | 9.2% | 5.0 | 0.59 |
    | 1963-1999 | 10.7% | 5.6 | 0.92 |
    | 2000-2019 | 2.1% | 0.5 | 0.11 |
    | 2000 to Sep 2026 | 2.5% | 0.7 | 0.14 |
    | 2020 to Sep 2026 | 3.7% | 0.6 | 0.24 |

  - The compounded return was 0.8% a year from 2000 to Sep 2026.
- **Crashes are large and come when the market rebounds** (UMD, LS, gross) [computed]:
  - 2009: -49% from March to May, -34% in April alone, -52.8% for the calendar year.
  - 2020-21: -12.6% in November 2020 (the vaccine rally), -23% from November 2020 to March 2021.
  - 2023: -16.2% in January 2023, -20.5% for the year.
  - 1932: -74% over July and August.
  - Maximum drawdown: -78% for 1927-2026, -58% since 2000.
  - Daniel & Moskowitz report that from March to May 2009 the loser decile rose 163% while the winner decile rose 8% [full text, working-paper version].
- **Published anomalies decay, but they do not disappear.**
  - McLean & Pontiff (2016), 97 predictors: returns are 26% lower out of sample and 58% lower after publication [full text].
  - Jensen, Kelly & Pedersen (2023): 82.4% of US factors replicate. The average alpha falls from 0.49% a month in sample to 0.26% a month after the original sample, a 47% decline [full text].
- **For a large-cap long-only investor, the best live index record is close to zero excess return.**
  - MSCI USA Momentum (LO, index, no costs) beat MSCI USA by 2.5% a year since June 1994: 13.12% against 10.64%, net-dividend returns to 30 Oct 2026. But the index launched in February 2013, and over its live calendar years 2014-2025 it beat MSCI USA by only **0.44% a year** [computed from the factsheet's annual returns].
  - Tracking error is 8.55%, maximum drawdown 56.2%, and turnover 113% a year [factsheet].
- **Momentum works in large caps, but less well since 2000** (French size-split portfolios, LS, gross) [computed]:

  | Period | Large-cap momentum | Small-cap momentum |
  |---|---|---|
  | 1927-1999 | 7.7% a year | 10.7% a year |
  | 2000-2026 | 1.1% a year | 3.9% a year |

  - The long-only version among large caps: the top-30% large-cap winners beat the market by 3.95% a year in 1927-1999 and by 0.55% a year in 2000-2026, with about 7% tracking error.
  - AQR (Asness et al. 2014): for 1991-2013, momentum among large caps had a Sharpe of 0.24, against 0.45 among small caps [full text].
- **Trading costs are manageable for an institution.**
  - AQR's live large-cap momentum fund (2009-2016) lost 12 bps a year to trading costs and 44 bps to fees. It still returned 14.32% a year net, 0.87% a year above its own index (whose return is gross of costs) [full text].
  - Novy-Marx & Velikov (1963-2013) estimate that costs take about half the gross return of a naive academic decile momentum strategy: 1.33% a month gross, 0.68% a month net [full text].
- **What improves momentum, by strength of evidence:**
  - Volatility scaling of momentum survives the Cederburg et al. (2020) out-of-sample critique. In their direct comparisons, volatility management improved all 9 momentum strategies, 5 of them significantly, even though it fails for most of the other 103 strategies [full text].
  - Residual momentum, Frog-in-the-Pan and the 52-week high each have positive in-sample evidence. I saw that evidence mostly in abstracts and summaries.
- **A realistic expectation (my synthesis of the sources, not a figure any one source states):**
  - Excess return: about **0% to 2% a year gross** over the S&P 500.
  - Tracking error: 7-10%, and likely more with only 20 stocks.
  - Information ratio: about 0.1-0.3.
  - Losing stretches of many years are likely, and so are occasional single months of -10% or worse against the index.
  - AQR's authors themselves put the historical long-only gross excess return of momentum at "around 1.0% to 1.5% per year" (Israel, Moskowitz, Ross & Serban 2021) [full text].

---

## 1. Long-short US momentum (UMD/WML) by era

### 1.1 Kenneth French's UMD factor [computed]

- **Source:** Kenneth R. French Data Library, `F-F_Momentum_Factor_CSV.zip`, built from the 202609 CRSP database, monthly data from 1927-01 to 2026-09. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- **Construction:** six value-weighted size and prior-return (months t-12 to t-2) portfolios, using NYSE 30th/70th percentile breakpoints. UMD is the average of the two winner portfolios (small and big) minus the average of the two loser portfolios.
- **Type:** LS, gross, no costs.

| Period | Months | Mean per year (arithmetic) | Compounded per year | Volatility per year | Sharpe | t-stat | Max drawdown | Worst month |
|---|---|---|---|---|---|---|---|---|
| 1927-01 to 2026-09 | 1197 | 7.41% | 6.07% | 16.3% | 0.46 | 4.55 | -78.4% | -52.6% (Aug 1932) |
| 1927-01 to 1999-12 | 876 | 9.22% | 8.05% | 15.7% | 0.59 | 5.01 | -78.4% | -52.6% |
| 1963-01 to 1999-12 | 444 | 10.69% | 10.47% | 11.7% | 0.92 | 5.57 | -20.3% | -13.8% |
| 1994-01 to 2026-09 | 393 | 4.50% | 3.07% | 16.7% | 0.27 | 1.54 | -57.8% | -34.4% |
| 2000-01 to 2019-12 | 240 | 2.10% | 0.29% | 18.4% | 0.11 | 0.51 | -57.8% | -34.4% (Apr 2009) |
| 2000-01 to 2026-09 | 321 | 2.50% | 0.84% | 17.7% | 0.14 | 0.73 | -57.8% | -34.4% |
| 2010-01 to 2026-09 | 201 | 3.38% | 2.58% | 12.8% | 0.26 | 1.08 | -25.4% | -16.2% |
| 2020-01 to 2026-09 | 81 | 3.68% | 2.52% | 15.3% | 0.24 | 0.62 | -25.4% | -16.2% (Jan 2023) |

The Sharpe column is the arithmetic mean divided by volatility, so it is close to a Sharpe ratio but not the same as one computed on excess returns.

UMD calendar-year returns since 2020 [computed]:

| Year | Return |
|---|---|
| 2020 | -0.9% |
| 2021 | -2.9% |
| 2022 | +20.2% |
| 2023 | -20.5% |
| 2024 | +18.5% |
| 2025 | -2.2% |
| 2026, Jan to Sep | +11.0% |

Earlier years:
- 2009: -52.8%.
- 2016: -18.2%.
- 2015: +21.1%.

Crash windows (UMD, compounded) [computed]:
- March to May 2009: -49.4%.
- March to September 2009: -56.4%.
- July to August 1932: -74.2%.
- November 2020: -12.6%.
- November 2020 to March 2021: -23.0%.
- The ten worst months since 1927 include April 2009 (-34.4%), January 2001 (-25.4%), November 2002 (-16.5%) and January 2023 (-16.2%).

Not covered: French's data ends in September 2026. The MSCI factsheet in section 3.1 shows a large momentum loss in **October 2026**: MSCI USA Momentum returned -10.87% against -0.99% for MSCI USA (LO index, net dividends). That month is not in the UMD figures above.

### 1.2 Daniel & Moskowitz, "Momentum crashes" [full text, NBER WP 20439 version]

- **Source:** Kent Daniel and Tobias J. Moskowitz, "Momentum Crashes", NBER Working Paper 20439 (August 2014); published in the *Journal of Financial Economics* 122(2), 2016. https://www.nber.org/papers/w20439
- **Version read:** the working paper, with sample 1927:01 to 2013:03. I did not check the published version's tables.
- **Strategy:** WML, LS decile (top minus bottom decile), value-weighted, gross.

Findings:
- The winner decile earned 15.3% a year above the T-bill rate, and the loser decile -2.5% a year. The market earned 7.6%.
- WML had a Sharpe of 0.71, against 0.40 for the market.
- WML's beta was -0.58, giving a CAPM alpha of 22.3% a year (t = 8.5).
- WML's monthly skewness was -4.70.
- The two worst WML months were July and August 1932, when the loser decile returned 232% and the winner decile 32%.
- From March to May 2009, the loser decile rose 163% and the winner decile 8%.
- The two largest sustained drawdowns ran from June 1932 to December 1939 and from March 2009 to March 2013.
- Crashes come in "panic" states: after market declines, when volatility is high, and at the same time as market rebounds.
- A dynamic strategy that scales WML by forecasts of its mean and variance "approximately doubles the alpha and Sharpe Ratio of a static momentum strategy". The paper reports that the dynamic strategy reaches an annualized Sharpe of 1.18 in one specification.

---

## 2. Post-publication decay

### 2.1 McLean & Pontiff (2016) [full text]

- **Source:** R. David McLean and Jeffrey Pontiff, "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance* 71(1), 2016, pp. 5-32. DOI 10.1111/jofi.12365. Copy read: https://www.gwern.net/doc/economics/2016-mclean.pdf
- **Sample:** 97 cross-sectional predictors, with data ending in 2013. All results are LS and gross.

Findings, quoted from the abstract:
- "Portfolio returns are 26% lower out-of-sample and 58% lower post-publication."
- The out-of-sample decline "is an upper bound estimate of data mining effects."
- "We estimate a 32% (58%-26%) lower return from publication-informed trading."
- Decay is larger for predictors with higher in-sample returns.
- Returns remain higher in stocks with high idiosyncratic risk and low liquidity, which points to limits to arbitrage.
- The paper reports no momentum-specific decay figure. It notes that Jegadeesh & Titman (2001) found momentum returns *increased* after their 1993 paper.

### 2.2 Jensen, Kelly & Pedersen (2023) [full text]

- **Source:** Theis Ingerslev Jensen, Bryan Kelly and Lasse Heje Pedersen, "Is There a Replication Crisis in Finance?", *Journal of Finance* 78(5), 2023, pp. 2465-2518. DOI 10.1111/jofi.13249. Open copy: https://research-api.cbs.dk/ws/portalfiles/portal/95651880/theis_ingerslev_jensen_et_al_is_there_a_replication_crisis_in_finance_publishersversion.pdf
- **Sample:** 153 factors in 93 countries. US data from CRSP starting in 1926; most other developed countries from 1986. Results are LS and gross.

Findings:
- The replication rate of US factors is 82.4%.
- By size group, the replication rate is 77.3% among mega caps and 79.8% among large caps.
- 11 of the 13 factor themes replicate at a rate of 50% or better. The exceptions are low leverage and size. Momentum is one of the 13 themes. I did not extract its theme-level replication rate, which is shown only in a figure.
- Decay: "the average in-sample alpha is 0.49% per month and the average out-of-sample alpha is 0.26% when looking postoriginal sample, implying a decline of 47%."
- Regressing out-of-sample alphas on in-sample alphas gives slopes of 0.26 to 0.57, with t-statistics of 3.5 to 5.3. That is, the factors are real but shrink.
- The authors say there "appears to be some decay of the strongest factors that could be due to arbitrage or data mining."

### 2.3 Ilmanen, Israel, Lee, Moskowitz & Thapar (2021) [abstract / secondary]

- **Source:** "How Do Factor Premia Vary Over Time? A Century of Evidence", *Journal of Investment Management* 19(4), 2021. https://papers.ssrn.com/abstract=3400998
- **Coverage:** value, momentum, carry and defensive factors in six asset classes over about a century. Results are LS.
- **Finding, from the search summary of the abstract (not verified in the text):** premia are about 30% lower out of sample, which the authors attribute more to overfitting than to arbitrage.

---

## 3. Long-only momentum: what an investor can actually get

### 3.1 MSCI USA Momentum Index vs MSCI USA [full text of the factsheet]

- **Source:** MSCI, "MSCI USA Momentum Index (USD)" factsheet, 30 Oct 2026. https://www.msci.com/documents/10199/255599/msci-usa-momentum-index-usd-net.pdf
- **Type:** LO, index, net-dividend returns. No trading costs or fees.
- **Backtest:** the index was launched on 15 Feb 2013. Data before that date is back-tested.
- **Construction (from the factsheet):** 125 constituents drawn from MSCI USA (514 constituents). I recall that the index ranks on 6- and 12-month risk-adjusted momentum, but I did not check that against the methodology document.

Annualized returns to 30 Oct 2026:

| | 1 yr | 3 yr | 5 yr | 10 yr | Since 30 Jun 1994 |
|---|---|---|---|---|---|
| MSCI USA Momentum | 12.15 | 26.47 | 8.59 | 14.75 | 13.12 |
| MSCI USA | 11.21 | 23.00 | 11.13 | 14.86 | 10.64 |

Risk, 1 Jun 1994 to 30 Oct 2026:
- Beta: 0.96.
- Tracking error: 8.55%.
- Turnover over the last 12 months: 112.67%, against 2.99% for MSCI USA.
- Volatility over 10 years: 18.58%, against 15.57%.
- Sharpe since 1994: 0.66, against 0.57.
- Maximum drawdown: 56.18% (26 Dec 2007 to 9 Mar 2009), against 55.36% for MSCI USA.

Calendar-year returns (Momentum vs MSCI USA):

| Year | MSCI USA Momentum | MSCI USA |
|---|---|---|
| 2013 | 34.03 | 31.79 |
| 2014 | 14.25 | 12.69 |
| 2015 | 8.70 | 0.69 |
| 2016 | 4.64 | 10.89 |
| 2017 | 37.24 | 21.19 |
| 2018 | -2.02 | -5.04 |
| 2019 | 27.44 | 30.88 |
| 2020 | 29.18 | 20.73 |
| 2021 | 12.64 | 26.45 |
| 2022 | -17.87 | -19.85 |
| 2023 | 8.98 | 26.49 |
| 2024 | 31.99 | 24.58 |
| 2025 | 17.34 | 17.31 |

Excess return over MSCI USA [computed by compounding the calendar-year returns above]:

| Period | Excess per year | Note |
|---|---|---|
| Since 1994 | +2.48% | mostly back-tested |
| 2014-2025 | **+0.44%** | live, full years after launch |
| 2016-2025 | -0.50% | |
| 2020-2025 | -2.17% | |

- Momentum beat MSCI USA in 9 of the 13 years 2013-2025.
- The standard deviation of the annual excess return was 9.2 points.
- The worst relative years were 2023 (-17.5 points) and 2021 (-13.8 points).
- The index's construction is MSCI's own, so its results apply to this strategy only by analogy.

### 3.2 French data: long-only winners vs the market [computed]

- **Source:** French Data Library, `6_Portfolios_ME_Prior_12_2` and `10_Portfolios_Prior_12_2` (value-weighted), compared with the market (Mkt-RF plus RF from `F-F_Research_Data_Factors`).
- **Type:** LO portfolio minus market, gross, no costs.
- "Big Hi" is the large-cap winner portfolio: above the NYSE median size and in the top 30% on prior return.

| Period | Big Hi minus market, per year | Tracking error | t-stat | Top decile (all sizes) minus market | Tracking error |
|---|---|---|---|---|---|
| 1927-1999 | 3.95% | 6.7% | 5.1 | 7.98% | 11.6% |
| 1963-1999 | 3.95% | 6.1% | 4.0 | 9.19% | 10.6% |
| 2000-2019 | 0.61% | 7.2% | 0.4 | 2.01% | 12.6% |
| 2000-2026/09 | 0.55% | 7.2% | 0.4 | 3.45% | 14.2% |
| 2010-2026/09 | 0.46% | 6.0% | 0.3 | 4.48% | 13.5% |
| 2020-2026/09 | 0.37% | 7.3% | 0.1 | 7.74% | 18.1% |

- Worst cumulative relative drawdown, compounded from the monthly differences:
  - Big Hi: -31% over 1927-1999 and -22% since 2000.
  - Top decile: -50% over 1927-1999 and -33% since 2000.
- The top-decile portfolio has done better since 2000, but it includes smaller stocks than the S&P 500, and its tracking error is about twice as large.

### 3.3 AQR: Asness, Frazzini, Israel & Moskowitz (2014), "Fact, Fiction and Momentum Investing" [full text]

- **Source:** *Journal of Portfolio Management*, 40th Anniversary Issue, 2014. https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/JPM-Fact-Fiction-and-Momentum-Investing.pdf
- **Data:** French data. Results are LS and gross.

Findings:
- Over 1927-2013, UMD averaged 8.3% a year (Sharpe 0.50), against HML 4.7% and SMB 2.9%.
- The long and short sides contributed about equally: the long side 5.5% and the short side 5.1% of the 10.6% total, in their regression decomposition.
- Over the full sample, momentum averaged 9.8% a year within small caps and 6.8% a year within large caps.
- Over 1991-2013, the Sharpe was 0.24 among large caps and 0.45 among small caps.
- A 4.5% a year large-cap and 8.1% a year small-cap gross momentum premium for 1991-2013 appears in a search summary of this paper. **I did not locate it in the text. Not verified.**
- On costs, the paper relies on Frazzini, Israel & Moskowitz (section 4.2).

### 3.4 AQR's live long-only funds: Israel, Moskowitz, Ross & Serban (2021) [full text]

- **Source:** "Putting an Academic Factor into Practice: The Case of Momentum", draft of 25 June 2021. https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2021/08/Putting-and-Academic-Factor-Into-Practice.pdf

Historical, Table 1 (January 1990 to December 2016, gross):

| Measure | Return per year | Sharpe | Alpha to FF3, per year |
|---|---|---|---|
| UMD, all stocks (LS) | 6.2% | 0.37 | n/a |
| UMD within the Russell 1000 (LS) | 4.21% | 0.26 | 7.2% (t = 2.96) |
| Long-only "U" leg within the Russell 1000, excess of T-bills | 6.82% | n/a | 2.5% (t = 2.14) |
| AQR US Large Cap Momentum Index, excess of T-bills | 8.59% | 0.51 | 2.3% (marginally significant) |

- The authors' summary of long-run long-only evidence: "a gross information ratio of around 0.3 (relative to the market factor) and gross average return of around 2% to 3% per year over the market, size, and value benchmarks."
- Later in the paper: "the gross average historical excess return of momentum is around 1.0% to 1.5% per year."

Live funds (31 Jul 2009 to 31 Dec 2016, LO, net):
- The US Large Cap momentum fund returned **14.32% a year net**, which is 0.87% a year *above* its momentum index. The index's return is gross of costs.
- The decomposition of that difference:
  - fees: -44 bps;
  - trading costs: -12 bps;
  - portfolio construction: +1.42%. The funds rebalance monthly, use a 60/20/20 blend of price, earnings and residual momentum, and weight stocks by size and signal.
- Realized trading cost averaged 12.61 bps per dollar traded, at about 84% turnover a year.
- The paper does not give the fund's excess return over the Russell 1000 in the text I read.
- AMOMX against the Russell 1000 since 2009: a search summary of AQR's factsheet gave 14.98% a year net against 15.38% for the Russell 1000, to 30 Sep 2025. **Not verified.** When I fetched AQR's page, it showed a "Large Cap Multi-Style Fund" and the note "Effective May 4, 2026, the Fund's principal investment strategies changed." The standalone momentum fund's current record could therefore not be confirmed.

### 3.5 Alpha Architect / Gray & Vogel, *Quantitative Momentum* (Wiley, 2015)

- **Document:** Alpha Architect, "Quantitative Momentum Indexes (QM and IQM)", deck dated 30 Sep 2019 [full text; the tables are mostly images].
- **Method:**
  - Universe: about the top 1,000 US stocks by market cap.
  - Ranking: 12-1 month momentum, then a "frog-in-the-pan" consistency filter.
  - Concentration: about 50 stocks.
  - Rebalancing: quarterly, at the end of February, May, August and November ("smart rebalance" for seasonality).
- **The one table I could read:** CAGR 15.97% for the "smart" rebalance dates against 15.06% for the "dumb" dates, over 1927-2014. The results are hypothetical and gross, before fees and costs. The deck does not compare these returns with a benchmark in text.
- **Book headline:** a blog review says high-quality momentum beat the S&P 500 by "more than seven percentage points annually" over 1927-2014. **Secondary, not verified.** Source: https://readingthemarkets.blogspot.com/2016/12/gray-and-vogel-quantitative-momentum.html
- **Live ETF, QMOM:**
  - Record: 10.59% a year at NAV since inception on 1 Dec 2015, to 31 Oct 2026. Ten-year return 12.06%. Expense ratio 0.28%. About 50 stocks. Source: https://funds.alphaarchitect.com/qmom
  - Comparison: the CRSP value-weighted market returned 14.47% a year from December 2015 to September 2026 [computed, French data; one month shorter than the QMOM window].
  - Result: the live, concentrated, net-of-fee version **trailed the market by roughly 3.5-4 points a year**.
  - Caveats: QMOM is not limited to the S&P 500, and its benchmark is not stated on the page.

### 3.6 S&P 500 Momentum Index

- S&P Dow Jones Indices' pages returned HTTP 403 to every fetch, so **nothing on this index is verified**.
- A search summary of the S&P DJI document "Momentum: A Practitioner's Guide" (data to 30 Jun 2026) reported a 10-year annualized return of 21.56% for the momentum index against 15.51% for the S&P 500, and 14.07% since its start. The summary itself flagged that the column mapping was ambiguous. Do not use these figures without checking the PDF: https://www.spglobal.com/spdji/en/documents/education/education-momentum-a-practioners-guide.pdf

---

## 4. Large vs small caps, and implementation costs

### 4.1 Size

French size-split momentum, LS, gross [computed]:

| Period | Big Hi minus Big Lo | Small Hi minus Small Lo |
|---|---|---|
| 1927-1999 | 7.72% a year (t = 3.8) | 10.71% a year (t = 5.9) |
| 1963-1999 | 6.95% | 14.41% |
| 2000-2026/09 | 1.12% (t = 0.3) | 3.88% (t = 1.1) |
| 2010-2026/09 | 1.10% | 5.68% (t = 2.0) |
| 2020-2026/09 | -0.03% | 7.42% |

- **Large-cap momentum has been close to zero, long-short, since 2000.** Small-cap momentum has been somewhat stronger, gross of costs.
- **Israel & Moskowitz (2013)** [abstract], "The role of shorting, firm size, and time on market anomalies", *Journal of Financial Economics* 108(2), pp. 275-301. https://econpapers.repec.org/RePEc:eee:jfinec:v:108:y:2013:i:2:p:275-301
  - Sample: 86 years of US data.
  - Momentum profits show "no reliable relation with size".
  - The long side accounts for about half of momentum profits.
  - The value premium, by contrast, is weak among the largest stocks.
- **Jensen, Kelly & Pedersen (2023)** [full text]: the factor replication rate in mega and large caps (77-80%) is close to the overall US rate (82%).
- **Asness et al. (2014)** [full text]: for 1991-2013, the large-cap momentum Sharpe of 0.24 compares with 0.45 in small caps (section 3.3).

### 4.2 Costs

**Frazzini, Israel & Moskowitz, "Trading Costs of Asset Pricing Anomalies"** [full text of the 5 Dec 2012 draft]
- Source: https://conference.nber.org/conf_papers/f68262/f68262.pdf ; AQR page: https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies
- Data: nearly $1 trillion of live trades in 19 developed markets, 1998-2011.
- US UMD:
  - trading cost of 3.51% a year, at 127% monthly turnover and about 23 bps of market impact per dollar traded;
  - break-even fund size of $52 billion in the US and $89 billion globally;
  - optimized versions, within 1% tracking error, reach a global break-even size of $122 billion.
- Later versions use $1.7 trillion of trades. That comes from a search summary; **I did not read a later version.**

**Novy-Marx & Velikov (2016), "A Taxonomy of Anomalies and Their Trading Costs"** [full text of the August 2015 version]
- Published in *Review of Financial Studies* 29(1), pp. 104-147. Source: https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf
- Sample: July 1963 to December 2013, value-weighted NYSE-decile LS portfolios, using effective spreads.
- Momentum:
  - 1.33% a month gross (t = 4.80);
  - turnover 34.5% a month;
  - costs 0.65% a month;
  - **0.68% a month net (t = 2.45)**;
  - net four-factor alpha 0.40% a month.
- A UMD-like factor with a buy/hold spread (1973-2012): 0.77% a month gross, 0.26% a month costs, 0.51% a month net.
- Capacity: momentum's profitability "disappears when roughly $5 billion of new capital, on each the long and short sides, pursues the strategy". This is far below Frazzini, Israel & Moskowitz's figure, because the two papers measure costs differently.
- The buy/hold spread is "the most effective cost mitigation technique": enter positions on a stricter rule than the one for keeping them.

**AQR live funds** (section 3.4): 12 bps a year trading cost for US large caps over 2009-2016, at about 84% turnover a year.

**Relevance here:** with 20 S&P 500 stocks rebalanced monthly, spreads are small. But turnover is likely to be high, and it was not measured here. A buy/hold buffer of the kind Novy-Marx & Velikov describe is the documented way to cut it.

---

## 5. Improving momentum

**Volatility scaling**
- Barroso & Santa-Clara (2015), "Momentum has its moments", *Journal of Financial Economics* 116(1), pp. 111-120. https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120
  - [abstract]: managing momentum's risk "virtually eliminates crashes and nearly doubles the Sharpe ratio".
  - A Sharpe of 0.53 rising to 0.97 (1927-2011, gross) appears only in secondary summaries (Swedroe on ETF.com; CXO Advisory). **Not verified.**
- Cederburg, O'Doherty, Wang & Yan (2020), "On the performance of volatility-managed portfolios", *Journal of Financial Economics* 138(1), pp. 95-117 [full text]. https://www.lehigh.edu/~xuy219/research/COWY.pdf
  - Across 103 strategies, volatility-managed versions "do not systematically outperform" the originals.
  - Real-time combination strategies generally earn lower Sharpe ratios.
  - **The exception is momentum:** "Volatility management improves performance for every momentum strategy, and five of the nine performance differences are statistically significant at the 5% level."
  - So the critique applies to volatility scaling in general, not to momentum.
  - These are LS results. For a long-only portfolio, the equivalent is scaling the active bet or the equity exposure. I found no test of that.

**Daniel & Moskowitz dynamic momentum:** see section 1.2. The paper says it roughly doubles the Sharpe ratio (LS, gross).

**Residual momentum**
- Blitz, Huij & Martens (2011), "Residual momentum", *Journal of Empirical Finance* 18(3), pp. 506-521 [abstract]. https://econpapers.repec.org/RePEc:eee:empfin:v:18:y:2011:i:3:p:506-521
  - Ranking on residuals from a Fama-French regression cuts time-varying factor exposures.
  - Risk-adjusted profits are "about twice as large" as for total-return momentum.
- Blitz, Hanauer & Vidojevic (2020), "The idiosyncratic momentum anomaly", *International Review of Economics & Finance* 69, pp. 932-957 [abstract / secondary]: idiosyncratic momentum is not explained by conventional momentum.
- AQR's live funds put 20% of the signal on residual momentum (section 3.4).

**Frog-in-the-Pan**
- Da, Gurun & Warachka (2014), "Frog in the Pan: Continuous Information and Momentum", *Review of Financial Studies* 27(7) [full text].
- Sample: 1927-2007, six-month holding period, LS, gross.
- Momentum falls "monotonically from 5.94% for stocks with continuous information ... to -2.07% for stocks with discrete information", with t = 8.54 for the difference.
- Alpha Architect's QM index uses this filter.

**52-week high**
- George & Hwang (2004), "The 52-Week High and Momentum Investing", *Journal of Finance* 59(5), pp. 2145-2176 [abstract only].
- Nearness to the 52-week high "dominates and improves upon" past returns as a forecast, and it does not reverse in the long run.
- I did not see their return figures.

**Time-series vs cross-sectional**
- Goyal & Jegadeesh (2018), *Review of Financial Studies* 31(5), pp. 1784-1824 [abstract]: for individual stocks, time-series momentum's apparent edge over cross-sectional momentum is "largely due to" its time-varying net long position.
- Huang, Li, Wang & Zhou (2020), "Time series momentum: Is it there?", *Journal of Financial Economics* 135(3), pp. 774-794 [abstract]: asset-by-asset evidence is weak, and a time-series strategy performs "virtually the same" as one based on historical sample means.
- For this strategy, the 50-day EMA filter is a time-series element. These papers suggest that much of the benefit of such a filter is a market-timing (net exposure) effect rather than a stock-selection effect. Neither paper tests a filter of this kind.

**Factor momentum**
- Ehsani & Linnainmaa (2022), "Factor Momentum and the Momentum Factor", *Journal of Finance* 77(3), pp. 1877-1919.
- [NBER WP 25551 full text]: the average factor earns 1 bp a month after a losing year and 53 bps after a winning year.
- [published abstract]: "momentum is not a distinct risk factor—it times other factors." A search summary gives the published figures as 6 bps and 51 bps. **Not verified.**

**Momentum in the 2020s**
- The French data shows large swings rather than a steady premium: +20% in 2022, -20% in 2023, +18% in 2024.
- Since 2020, large-cap long-short momentum has averaged about zero.
- MSCI USA Momentum lagged MSCI USA by 2.2% a year over 2020-2025, and by 10 points in October 2026 alone.
- Crowding is a reported concern. MSCI and press reports describe crowding in AI-linked momentum names during 2024-2026, and an MSCI blog describes a mid-2025 "quant wobble" (https://www.msci.com/research-and-insights/blog-post/unraveling-summer-2025s-quant-fund-wobble). I saw these only in search summaries and did not verify their figures.

---

## 6. A realistic expected excess return for long-only large-cap US momentum

What the sources state:

| Source | Statement | Period | Type |
|---|---|---|---|
| Israel, Moskowitz, Ross & Serban (2021), AQR | "gross average historical excess return of momentum is around 1.0% to 1.5% per year"; elsewhere "a gross information ratio of around 0.3 ... gross average return of around 2% to 3% per year over the market, size, and value benchmarks" | long history; Table 1 covers 1990-2016 | LO, gross |
| Same paper, Table 1 | Long-only momentum leg within the Russell 1000: FF3 alpha 2.5% a year (t = 2.14) | 1990-2016 | LO, gross |
| MSCI factsheet [computed] | +2.48% a year since 1994 (mostly backtest); +0.44% a year live 2014-2025; tracking error 8.55% | 1994-2026 | LO index, no costs |
| French data [computed] | Large-cap winners minus market: +3.95% a year before 2000, +0.55% a year since 2000; tracking error about 7% | 1927-2026 | LO, gross |
| QMOM live | 10.59% a year net, against about 14.5% for the market | Dec 2015 to Oct 2026 | LO, net |
| McLean & Pontiff (2016); Jensen, Kelly & Pedersen (2023); Ilmanen et al. (2021) | Expect premia 30-58% below the published, in-sample figures | — | LS |

**Synthesis (mine, for this strategy):**
- **Excess return:** about **0% to 2% a year gross** over the S&P 500. The midpoint is around 1%, in line with AQR's own 1.0-1.5% figure. The live index records since 2013 sit at the bottom of the range, at about zero. Pre-2000 backtests (3-4% a year or more) should not be used as the expectation.
- **Tracking error:** 7-10% for diversified indices of 100 or more names. A 20-stock portfolio will be higher. I found no published figure for 20 stocks.
- **Information ratio:** about 0.1-0.3, so even a real edge of 1-2% a year will not be statistically distinguishable from zero for a decade or more.
- **Drawdowns:**
  - Relative drawdowns of 20-30% are documented: French large-cap winners, -22% relative since 2000.
  - Single-month losses of 10 points or more against the index happen: October 2026, -9.9 points for the MSCI index.
  - In absolute terms, the drawdown is about as deep as the market's: 56% for MSCI USA Momentum in 2007-09.
- **Net of costs:** institutional trading costs of about 0.1-0.5% a year. AQR measured 12 bps. Novy-Marx & Velikov's academic estimates are higher, but they apply to monthly-rebalanced, NYSE-decile long-short portfolios.

**What was not checked:**
- S&P 500 Momentum Index data (pages blocked).
- The published versions of Daniel & Moskowitz (2016) and Barroso & Santa-Clara (2015).
- The later, $1.7 trillion version of Frazzini, Israel & Moskowitz.
- Current AQR momentum fund figures.
- The tables in Gray & Vogel's book.
- George & Hwang's return figures.
- Any study of a 20-stock S&P 500 portfolio specifically.
- Whether the 50-day EMA and 52-week-high filters add value out of sample. No source tests that exact combination.

---

## Sources

1. Kenneth R. French Data Library: momentum factor, 6 size/prior-return portfolios, 10 prior-return portfolios, Fama/French 3 factors (CRSP 202609). https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
2. Daniel, K. & Moskowitz, T. (2014/2016), "Momentum Crashes", NBER WP 20439; *Journal of Financial Economics* 122(2). https://www.nber.org/papers/w20439
3. McLean, R.D. & Pontiff, J. (2016), "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance* 71(1), pp. 5-32. https://www.gwern.net/doc/economics/2016-mclean.pdf
4. Jensen, T.I., Kelly, B. & Pedersen, L.H. (2023), "Is There a Replication Crisis in Finance?", *Journal of Finance* 78(5), pp. 2465-2518. https://research-api.cbs.dk/ws/portalfiles/portal/95651880/theis_ingerslev_jensen_et_al_is_there_a_replication_crisis_in_finance_publishersversion.pdf
5. Ilmanen, A., Israel, R., Lee, R., Moskowitz, T. & Thapar, A. (2021), "How Do Factor Premia Vary Over Time? A Century of Evidence", *Journal of Investment Management* 19(4). https://papers.ssrn.com/abstract=3400998
6. MSCI (2026), MSCI USA Momentum Index (USD) factsheet, 30 Oct 2026. https://www.msci.com/documents/10199/255599/msci-usa-momentum-index-usd-net.pdf
7. Asness, C., Frazzini, A., Israel, R. & Moskowitz, T. (2014), "Fact, Fiction and Momentum Investing", *Journal of Portfolio Management* 40(5). https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/JPM-Fact-Fiction-and-Momentum-Investing.pdf
8. Israel, R., Moskowitz, T., Ross, A. & Serban, L. (2021), "Putting an Academic Factor into Practice: The Case of Momentum". https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2021/08/Putting-and-Academic-Factor-Into-Practice.pdf
9. Israel, R. & Moskowitz, T. (2013), "The role of shorting, firm size, and time on market anomalies", *Journal of Financial Economics* 108(2), pp. 275-301. https://econpapers.repec.org/RePEc:eee:jfinec:v:108:y:2013:i:2:p:275-301
10. Frazzini, A., Israel, R. & Moskowitz, T. (2012 draft), "Trading Costs of Asset Pricing Anomalies". https://conference.nber.org/conf_papers/f68262/f68262.pdf ; https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies
11. Novy-Marx, R. & Velikov, M. (2016), "A Taxonomy of Anomalies and Their Trading Costs", *Review of Financial Studies* 29(1), pp. 104-147. https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf
12. Barroso, P. & Santa-Clara, P. (2015), "Momentum has its moments", *Journal of Financial Economics* 116(1), pp. 111-120. https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 . Secondary summary: https://www.etf.com/node/94292.md
13. Cederburg, S., O'Doherty, M., Wang, F. & Yan, X. (2020), "On the performance of volatility-managed portfolios", *Journal of Financial Economics* 138(1), pp. 95-117. https://www.lehigh.edu/~xuy219/research/COWY.pdf
14. Blitz, D., Huij, J. & Martens, M. (2011), "Residual momentum", *Journal of Empirical Finance* 18(3), pp. 506-521. https://econpapers.repec.org/RePEc:eee:empfin:v:18:y:2011:i:3:p:506-521
15. Blitz, D., Hanauer, M. & Vidojevic, M. (2020), "The idiosyncratic momentum anomaly", *International Review of Economics & Finance* 69, pp. 932-957. https://econpapers.repec.org/RePEc:eee:reveco:v:69:y:2020:i:c:p:932-957
16. Da, Z., Gurun, U. & Warachka, M. (2014), "Frog in the Pan: Continuous Information and Momentum", *Review of Financial Studies* 27(7).
17. George, T. & Hwang, C.-Y. (2004), "The 52-Week High and Momentum Investing", *Journal of Finance* 59(5), pp. 2145-2176.
18. Goyal, A. & Jegadeesh, N. (2018), "Cross-Sectional and Time-Series Tests of Return Predictability: What Is the Difference?", *Review of Financial Studies* 31(5), pp. 1784-1824. https://ideas.repec.org/a/oup/rfinst/v31y2018i5p1784-1824..html
19. Huang, D., Li, J., Wang, L. & Zhou, G. (2020), "Time series momentum: Is it there?", *Journal of Financial Economics* 135(3), pp. 774-794. https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:3:p:774-794
20. Ehsani, S. & Linnainmaa, J. (2022), "Factor Momentum and the Momentum Factor", *Journal of Finance* 77(3), pp. 1877-1919; NBER WP 25551. https://www.nber.org/papers/w25551
21. Alpha Architect (2019), "Quantitative Momentum Indexes (QM and IQM)" deck, citing Gray, W. & Vogel, J. (2015), *Quantitative Momentum*, Wiley. QMOM fund page: https://funds.alphaarchitect.com/qmom
22. S&P Dow Jones Indices, "Momentum: A Practitioner's Guide" (could not be fetched). https://www.spglobal.com/spdji/en/documents/education/education-momentum-a-practioners-guide.pdf
23. MSCI blog, "Unraveling Summer 2025's Quant Fund Wobble" (seen only in a search summary). https://www.msci.com/research-and-insights/blog-post/unraveling-summer-2025s-quant-fund-wobble
