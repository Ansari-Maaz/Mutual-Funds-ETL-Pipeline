# Competitive landscape for US mutual fund / ETF data APIs (Twelve Data as reference)

Research date: 2026-11-17. Public pages only; no paid/restricted endpoints accessed. Page text was read via a summarizing fetch tool, so quotes are as relayed by that tool, not independently verified against raw HTML. Items not re-verified in Nov 2026 are marked STALE-RISK.

## 1. Twelve Data mutual fund endpoints, fields, plans, price; Morningstar attribution

### Takeaway
Twelve Data's rich mutual fund data (summary, performance, risk, ratings, composition, purchase info, sustainability) is gated to the Ultra plan ($999/mo) and up, at 200 credits per call (1000 for the combined call). Its docs name no source. Morningstar involvement could not be confirmed from public docs, but identifier format hints at it (inference).

### Cited Findings
- Endpoints: `/mutual_funds/list` (1 credit), `/mutual_funds/world` (1000), `/world/summary|performance|risk|ratings|composition|purchase_info|sustainability` (200 each), `/mutual_funds/family` and `/type` (1 each). There is no endpoint literally named "world/list". — [TD MF docs](https://twelvedata.com/docs/mutual-funds/mf-summary), [list](https://twelvedata.com/docs/mutual-funds/mutual-funds-list)
- List endpoint returns symbol, name, country, fund_family, fund_type, performance_rating, risk_rating, currency, exchange, mic_code. Basic/Grow/Pro get up to 50 records; full list (claimed 140,000+ funds) needs Ultra/Enterprise. Filters include isin, cusip, cik, figi (figi Ultra+). — [TD list docs](https://twelvedata.com/docs/mutual-funds/mutual-funds-list)
- Summary fields: name, fund_family, fund_type, currency, share_class_inception_date, ytd_return, expense_ratio_net, yield, nav, min_investment, turnover_rate, net_assets, overview, people (managers). — [TD docs](https://twelvedata.com/docs/mutual-funds/mf-performance)
- Performance: trailing_returns, annual_total_returns, quarterly_total_returns, load_adjusted_return (with category comparisons). Risk: alpha, beta, std, Sharpe, Treynor, R-squared each with category equivalent; valuation_metrics. Ratings: performance_rating, risk_rating, return_rating (0-5). Composition: major_market_sectors, asset_allocation, top_holdings, bond_breakdown (maturity, duration, credit quality). Purchase info: expenses, minimums incl. IRA, pricing (NAV, 12-month range), brokerages. Sustainability: score 0-100, ESG pillars, sustainable_investment flag. — [TD docs](https://twelvedata.com/docs/mutual-funds/mf-summary)
- World endpoints accept symbol, figi, isin, or cusip; `dp` 0-11, default 5. — [TD list docs](https://twelvedata.com/docs/mutual-funds/mutual-funds-list)
- Pricing: Basic $0 (800/day, 8/min), Grow $79, Pro $229, Ultra $999 per month (monthly billing; yearly saves 17%). Mutual fund NAV data listed under Pro; mutual fund "metrics" under Ultra. CUSIP and ISIN are paid add-ons. Page structured data shows different prices ($29/$99/$329), so the pricing page is internally inconsistent. — [TD pricing](https://twelvedata.com/pricing)
- Launch article: "200,000+ international funds from 50+ countries"; launched 2022-06-01; prices updated once daily after market close (article also says "real-time" elsewhere, inconsistent); no source named; US coverage not explicitly claimed. — [TD launch news](https://twelvedata.com/news/introducing-mutual-funds-apis)
- Attribution: the docs do not name Morningstar. Ratings are described as "calculated in-house by Twelve Data and from various financial institutions" (unnamed). — [TD docs](https://twelvedata.com/docs/mutual-funds/mf-summary)
- Doc sample: request symbol `1535462D` returns symbol `0P0001LCQ3` (JNL Small Cap Index Fund (I), Small Blend, exchange OTC, USD), NAV 10.09, net_assets 2,400,762,112, ytd_return -0.02986, expense_ratio_net 0.001. — [TD docs](https://twelvedata.com/docs/mutual-funds/mf-summary)

### Inferences
- The `0P...` ten-character symbol and fund_type labels such as "Small Blend" resemble Morningstar SecId and Morningstar category naming. This is an inference; no public Twelve Data statement confirms it. Treat "Morningstar-derived" as unconfirmed.
- For US funds, the full analytics feed costs at least $999/mo, so a cheaper, regulator-based product has a price gap to exploit.

### Gaps
- Per-field source attribution, NAV history depth, and US fund counts are not stated in public docs. Time-series docs mention "Mutual Fund" as a `type` but give no fund-specific notes ([TD time_series](https://twelvedata.com/docs/market-data/time-series)).

## 2. Competitor coverage claims (US mutual funds)

### Takeaway
Few providers document deep US mutual fund coverage. Intrinio and Xignite are explicit but enterprise-priced. FMP is strongest on SEC-derived holdings. Others are vague.

### Cited Findings
- Intrinio: open- and closed-end funds, NAVs, holdings, strategy, issuer, expenses and returns; 12+ years of history (full history a separate one-time charge); source Cannon Valley Research; daily; API and CSV; enterprise-only, NAVs need a separate license; no public prices. — [Intrinio](https://intrinio.com/products/mutual-fund-data)
- Xignite: NAV for US mutual funds, daily end-of-day, history back to 1994 (as stated by search snippet). — [Xignite](https://xignite.com/mutual-funds-data/)
- Tiingo: says its daily database covers 65,000+ securities including mutual funds and ETFs; the tiingo-python client deprecated a Mutual Funds endpoint in 2017 (may not reflect the current API). STALE-RISK. — [Tiingo daily](https://api.tiingo.com/services/tiingo/daily), [tiingo-python](https://tiingo-python.readthedocs.io/en/stable/history.html)
- FMP: mutual fund list ("registered with the SEC"), historical price (date, change, close), mutual fund disclosures/holdings (asset category, issuer, country, market value USD, % of portfolio), fund info (expense ratio, AUM). Holdings sit in higher tiers (a $149/mo annual tier listed; verify). No explicit NAV coverage claim found. — [FMP disclosures](https://site.financialmodelingprep.com/developer/docs/stable/mutual-fund-disclosures), [FMP insight](https://site.financialmodelingprep.com/insights/enterprise/etf-and-mutual-fund-data-apis-for-holdings-and-performance)
- EODHD: publishes fund pages mostly for European (EUFUND) funds in results; 2018 blog announced mutual funds in fundamentals feed. US NAV history depth not confirmed. — [EODHD example](https://eodhd.com/financial-summary/LU0135702214.EUFUND)
- Marketdata.app: daily and historical mutual fund prices "going back decades"; no counts or source stated. — [Marketdata.app](https://www.marketdata.app/data/funds/index.md)
- Polygon (now Massive) and Alpha Vantage: no public mutual fund NAV product found in search. Polygon's OTC equities are FINRA-sourced per one source. — [Massive](https://massive.com/blog/otc-stocks)

### Inferences
- Absence of a documented mutual fund endpoint at Polygon and Alpha Vantage is not proof of absence; docs were not directly verified.

### Gaps
- Morningstar Direct / Data API terms and pricing: not publicly documented, not researched (subscription/quote-only). Yahoo-derived providers: no official coverage claims (unofficial API). EODHD, Tiingo, Alpha Vantage, Polygon: US fund counts and ISIN/CUSIP/category availability not found. Direct fetch of EODHD docs returned 404.

## 3. Source and licensing statements; redistribution restrictions

### Takeaway
Only Intrinio names a fund-data source (Cannon Valley Research). Twelve Data names none for funds but its terms refer to unnamed "Third-Party Providers" and bar redistribution and competing products.

### Cited Findings
- TD Terms s.3.2(a): Third-Party Data "provided AS IS"; s.3.2(b): "Twelve Data does not control Third-Party Providers or their data quality"; s.3.2(e): Third-Party Providers are third-party beneficiaries with enforcement rights. — [TD Terms](https://twelvedata.com/terms)
- YCharts status page reports delayed mutual fund pricing from an upstream provider, showing vendor-chain dependence. — [YCharts incident](https://status.ycharts.com/incidents/wdkrcp5sy79b)

### Inferences
- Because TD data is stated to come from third parties, any parity with TD for licensed fields reflects the upstream vendor, not independent facts.

### Gaps
- No ICE/FactSet/Morningstar attribution found on public pages for any provider in this scope.

## 4. Gaps and complaints in public discussions

### Takeaway
Public evidence is thin and mostly indirect: delayed NAVs, flat-price artifacts, and upstream delays.

### Cited Findings
- Portfolio Performance forum: funds with delayed or weekly NAV show 0.00% daily change because a backward price lookup resolves both dates to the same NAV record. — [forum](https://forum.portfolio-performance.info/t/daily-change-in-price-for-funds-with-delayed-or-weekly-nav-reporting/39372)
- GnuCash list: Finance::Quote entering previous day's price as today's. — [GnuCash 2020](https://lists.gnucash.org/pipermail/gnucash-user/2020-June/091624.html)
- yfinance issue 2017: mutual fund ticker returns only top holdings, not full holdings; issue 2621 (Nov 2025): missing price history for one date across tickers, attributed to Yahoo side. — [#2017 via search](https://github.com/ranaroussi/yfinance/issues), [#2621](https://github.com/ranaroussi/yfinance/issues/2621)
- LSEG forum: "corrupted NAV data of mutual funds" thread (outside US-specific scope). — [LSEG](https://community.developers.lseg.com/discussion/133231/data-quality-issue-corrupted-nav-data-of-mutual-funds)
- TD docs themselves contain errors (request/response symbol mismatch; mis-described parameters; count 1000 with 50-record cap). — [TD docs](https://twelvedata.com/docs/mutual-funds/mutual-funds-list)

### Gaps
- No direct Reddit or Twelve Data forum threads on missing ISIN/category were retrieved; claims about those complaints are not supported here.

## 5. What an SEC-sourced product can credibly claim; structural limits

### Takeaway
Inference only: a regulator-sourced product can claim provenance, auditability, and cost advantages on public-fact fields, but cannot replicate licensed analytics.

### Cited Findings
- FMP already markets SEC-registered fund list and SEC-disclosure-style holdings, so SEC-derived holdings alone are not unique. — [FMP](https://site.financialmodelingprep.com/developer/docs/stable/mutual-fund-disclosures)

### Inferences
- Defensible differentiators: filing-level lineage (accession numbers) per value; full SEC-registered universe by series/class IDs (CIK, series, class ID) with ticker history; holdings by N-PORT with explicit as-of dates; low price versus $999/mo; clear redistribution rights.
- Structural limits: SEC filings lag (N-PORT public after delay; prospectus fees annual); no daily NAV from the SEC; no star ratings, Morningstar category, risk stats, ESG; ticker-to-class mapping needs care.

### Gaps
- Exact current N-PORT public-release lag and filing-based NAV coverage were out of scope and not researched here.

---

## Value parity with Twelve Data

### Takeaway
Fields that are public facts (issuer NAV, ticker, inception date, SEC-filed holdings, expense ratio from prospectus) should match a correctly sourced independent product within documented rounding and date conventions. Fields that are vendor-proprietary (category labels, star/risk ratings, risk statistics, ESG) cannot legitimately be reproduced from regulator data, and ingesting them from TD would breach its terms.

### Cited Findings (facts)
- Time series: values have datetime, open, high, low, close, volume; prices returned as strings; volume only "for applicable instruments"; `adjust` accepts all/splits/dividends/none, default `splits`; `dp` default -1 for time_series (auto from values), 0-11; daily data returned in exchange local time. History depth not stated. — [TD time_series](https://twelvedata.com/docs/market-data/time-series)
- World (fund analytics) endpoints: `dp` default 5. Dates are YYYY-MM-DD. Return fields look like decimals (ytd_return -0.02986) but docs do not say decimals vs percent. — [TD docs](https://twelvedata.com/docs/mutual-funds/mf-performance)
- Per-field underlying source, update timing, and date convention (valuation date vs publish date) for NAV, OHLC mapping, expense ratio, net assets, performance, etc.: NOT stated in public docs. Only statements: directory "updated daily"; launch article says prices update once daily after close; ratings partly "calculated in-house ... and from various financial institutions." — [TD list docs](https://twelvedata.com/docs/mutual-funds/mutual-funds-list), [launch](https://twelvedata.com/news/introducing-mutual-funds-apis)
- ISIN and CUSIP are paid add-ons on TD. — [TD pricing](https://twelvedata.com/pricing)
- TD Terms (https://twelvedata.com/terms), as relayed:
  - s.2.2(a): Customer may "Access, receive, process, and store Data solely for Internal Use."
  - s.2.3(g): prohibits "Store or cache Data beyond permitted timeframes specified in the Documentation."
  - s.2.3(b): no redistributing, reselling, sublicensing, or transferring "Data or access rights to third parties" except as a tier/add-on/agreement permits.
  - s.2.2(e): external display/redistribution only if "expressly authorized by a Redistribution Rights Add-On or separate written agreement."
  - s.17.1(f): prohibits "Resell access without authorization."
  - s.2.3(d): prohibits using the Platform to "build competitive products or services."
  - s.2.3(k): prohibits combining Data with other sources to create competing products "without permission."
  - s.16.1: retention only for the permitted subscription duration (subject to provider restrictions).
  - Benchmarking is not mentioned explicitly.
- Cross-provider causes of difference (documented in public discussions): delayed or weekly NAV reporting producing stale or repeated values ([Portfolio Performance](https://forum.portfolio-performance.info/t/daily-change-in-price-for-funds-with-delayed-or-weekly-nav-reporting/39372)); previous-day price entered as today's ([GnuCash](https://lists.gnucash.org/pipermail/gnucash-user/2020-June/091624.html)); upstream vendor pricing delays ([YCharts](https://status.ycharts.com/incidents/wdkrcp5sy79b)); documented TD `adjust` default of `splits` versus `all` (dividend-adjusted) ([TD time_series](https://twelvedata.com/docs/market-data/time-series)).

### Inferences
- Fields likely vendor-licensed (cannot be matched from SEC/issuer data): fund_type/category labels (resemble Morningstar categories), performance/risk/return ratings, alpha/beta/Sharpe/Treynor/R-squared with category comparisons, ESG scores, category return comparisons, brokerage lists, pricing "12-month range" as computed. Treat any match as coincidence or a signal of vendor-derived values.
- Plain public facts that should match if sourced correctly: ticker and share-class identity, issuer-published NAV for a given valuation date, share_class_inception_date, net/gross expense ratio (prospectus, with the fee-table date), net assets (as of a stated date; vendors may use different as-of dates), SEC-filed holdings (as of filing period end), ISIN/CUSIP (CUSIP is a licensed identifier by CUSIP Global Services; redistribution is restricted, so not a public fact in the legal sense).
- Plausible sources of mismatch, not confirmed by TD docs: NAV date label as valuation date vs next-day publish date; one NAV mapped to open=high=low=close (typical for single-price instruments, unverified for TD); rounding (dp default 5 or auto vs issuer's 2-4 decimals); dividend-adjusted vs raw NAV; share-class mapping (TD sample shows a fund-class keyed by a vendor ID, with "OTC" as exchange); ticker reuse after fund mergers or liquidations; currency (US funds mostly USD); returns as decimals vs percent; net assets as-of date differing from fund-level vs class-level.
- Legitimate parity-testing methodology (inference, with legal caution): (1) source values independently from issuer/SEC/other licensed feeds; (2) fetch reference values only within TD terms, e.g. a small QA sample on a paid plan for internal accuracy measurement, never stored beyond permitted timeframes, never fed into the product's dataset; (3) join on class ID/ticker plus valuation date, normalize units and rounding to the coarser precision; (4) report match rates by field, tolerance bands (NAV within rounding half-unit of the issuer's published decimals), and classify mismatches as date lag, adjustment, mapping, or true error; (5) adjudicate against the primary source (issuer/SEC), not TD; (6) exclude vendor-proprietary fields from parity targets. Whether any QA use of TD output is permitted given s.2.3(d)/(k) is a legal question; get counsel or written permission. Ingesting TD values to populate or "fix" your data is clearly outside the stated terms.

### Gaps
- Not found in public docs: TD per-field upstream source; NAV date convention; OHLC mapping for funds; rounding at source; history depth for fund time series; explicit benchmarking policy; the "permitted timeframes" for caching referenced in s.2.3(g) (defers to Documentation not seen). Terms text was obtained via summarizing fetch; verify wording on the live page. Not legal advice.
