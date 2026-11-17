# Twelve Data Mutual Funds API Gap Assessment

Reviewed the official pages supplied by the user on 2026-11-09. The generated reference documents these routes under `/mutual_funds`; FundFlow's local compatibility base is `/api/v1/mutual_funds`.

## Endpoint inventory and current FundFlow coverage

| Twelve Data endpoint | Documented scope | FundFlow source-backed coverage | Gap / implementation status |
| --- | --- | --- | --- |
| `GET /mutual_funds/list` | Daily directory; symbol, FIGI, ISIN, CUSIP, CIK, country, family/type, ratings, currency, exchange/MIC; paging, JSON/CSV | `funds`, profile `summary`, `ratings`, `market_data_metadata`; SEC CIK where known | Compatibility route added. FIGI is not stored. Family/type/rating/exchange values are nullable when no source snapshot supports them. Directory is FundFlow's universe, not Twelve Data's 140k catalog. |
| `GET /mutual_funds/world` | Summary + performance + risk + ratings + composition + purchase info + sustainability | Generic source-versioned `fund_profile_snapshots`; SEC N-PORT holdings and country-specific official snapshots | Compatibility route combines only existing datasets and reports `partial` when sections are absent. No vendor records are copied. |
| `GET /mutual_funds/world/summary` | Fund identity, family/type/currency, inception, returns, expense, yield, NAV, minimum, turnover, net assets, overview, managers | Canonical fund fields and official-source `summary`, `aum_history`, `expense_ratio_history`, `nav_history`, `fees`, `yields`, `performance` snapshots | Route added for source-backed `summary` snapshots. Still needs official-source adapters for globally comparable yield, turnover, minimums, manager tenures, and description where absent. |
| `GET /mutual_funds/world/performance` | Trailing, annual, quarterly, load-adjusted returns | `performance` snapshots; some country connectors store period returns | Route added. Coverage is country/source dependent; no synthetic period returns are generated from NAV. |
| `GET /mutual_funds/world/risk` | Alpha, beta, mean return, R-squared, standard deviation, Sharpe/Treynor, valuation metrics, category comparisons | `risk` snapshots and filed security-level holdings; limited source-specific risk grades | Route added. Most vendor metrics and peer/category values require a licensed or regulator-published source and remain unavailable unless present in an official-source snapshot. |
| `GET /mutual_funds/world/ratings` | Performance, risk, return ratings (0–5) | `ratings` snapshots; some sources publish other risk grades | Route added. Rating methodologies are provider-specific; no conversion from unrelated risk grades is claimed. |
| `GET /mutual_funds/world/composition` | Sector weights, asset allocation, top holdings, bond maturity/duration/credit quality | `portfolio_holdings` from filings (notably SEC N-PORT) and `composition` snapshots | Route added for source snapshots. Fund-level aggregation, sectors and bond analytics remain gaps where the filing/source does not publish them; share-class/series scope and report date must be retained. |
| `GET /mutual_funds/world/purchase_info` | Expense ratios, minimums, NAV/range/last month, brokerages | `fees`, `expense_ratio_history`, `nav_history` snapshots and canonical NAV history | Route added. Minimums and brokerage lists are not currently broadly sourced; NAV ranges can be computed only from a documented, complete window and are not fabricated. |
| `GET /mutual_funds/world/sustainability` | ESG score/pillars, sustainable-investment flag, covered corporate AUM | Generic snapshots only where a source supplies them | Route added. No broad official ESG dataset is integrated; unavailable unless a sourced snapshot exists. |
| `GET /mutual_funds/family` | Country-grouped fund-family values; optional country/family filter | `funds.provider` and source summary | Route added as distinct source-reported provider values. This is not claimed to be a complete taxonomy. |
| `GET /mutual_funds/type` | Country-grouped fund types; optional country/type filter | `funds.fund_type` and source summary | Route added as distinct source-reported fund types. Source classifications are preserved, not silently mapped to Twelve Data categories. |

## Response and provenance behavior

The compatibility routes use Twelve Data's route names and query keys where supported. Data comes only from FundFlow's database. Profile sections return a `mutual_fund` object and a `_fundflow` provenance extension identifying source, source URL, report date, and retrieval time. Missing sections return HTTP 404 with `data_unavailable`; the full-data route returns `partial` and lists absent sections. Ambiguous tickers return HTTP 409; use ISIN/CUSIP to select a share class. These controls prevent unknown data from appearing as an exact match.

Directory requests accept `symbol`, `isin`, `cusip`, `cik`, `country`, `fund_family`, `fund_type`, `page`, `outputsize`, `format`, and `delimiter`. FIGI and Twelve Data's broad market taxonomy are not yet available in FundFlow. Ratings filters are not applied unless ratings are present; avoid interpreting null as zero.

## Required official-source work to close the remaining gaps

1. Resolve each fund/share class to a regulator or fund-company identifier (SEC CIK/series/class for US; official national register identifiers elsewhere); retain source and share-class scope.
2. Import NAV history on each source's stated valuation calendar and preserve report/valuation date, currency, source URL, and retrieval timestamp.
3. Add dated official summary, return, expense, yield, distribution, and purchase-minimum datasets where publishers/regulators actually provide them.
4. Expand US SEC N-PORT coverage while labeling filing period, series-level versus class-level scope, and filing publication lag. Do not compare a filed quarterly portfolio as if it were a same-day vendor snapshot.
5. Add official sector/asset allocation or sustainability sources only when definitions, dates, licensing, and coverage can be recorded.
6. Keep field-level comparison reports split into exact match, normalized match, mismatch, missing from FundFlow, unavailable from source/subscription, and date/scope-incomparable.

Twelve Data's reference describes its directory as 1 credit and data endpoints as up to 1,000 credits for full data or 200 credits per individual premium section, with some endpoints plan-gated. The FundFlow compatibility routes do not incur Twelve Data API credits. See [official mutual-funds reference](https://twelvedata.com/docs/mutual-funds), [directory](https://twelvedata.com/docs/mutual-funds/mutual-funds-list), [full data](https://twelvedata.com/docs/mutual-funds/mf-all-data), [summary](https://twelvedata.com/docs/mutual-funds/mf-summary), [performance](https://twelvedata.com/docs/mutual-funds/mf-performance), [risk](https://twelvedata.com/docs/mutual-funds/mf-risk), [ratings](https://twelvedata.com/docs/mutual-funds/mf-ratings), [composition](https://twelvedata.com/docs/mutual-funds/mf-composition), [sustainability](https://twelvedata.com/docs/mutual-funds/mf-sustainability), [families](https://twelvedata.com/docs/mutual-funds/mutual-fund-family-list), and [types](https://twelvedata.com/docs/mutual-funds/mutual-fund-type-list).

## Parity scope after the official-source review

FundFlow does not import Twelve Data values. Matching a licensed aggregator record
for record is therefore not a realistic or honest target: several of its fields are
provider-proprietary or plan-gated. A current `basic` key returns HTTP 403 for
`/mutual_funds/world/summary|performance|risk|ratings|composition|purchase_info|sustainability`,
so those sections cannot even be compared, and the directory endpoint is capped at
50 rows per request rather than the documented 1,000.

What FundFlow can and does match from official sources:

- NAV values that are published by the issuer or the official dissemination venue,
  retained with valuation date, currency, source URL and retrieval time.
- Fund identity from SEC series/class data, plus adviser, administrator, custodian,
  transfer agent, pricing service, accountant and underwriter from Form N-CEN.
- Reported classification flags (ETF, index, money market, target date, fund of
  funds) and official net assets.
- Filed portfolio holdings from N-PORT/N-MFP.

What stays non-identical by definition:

- Twelve Data's fund-type taxonomy and performance/risk ratings are proprietary
  vendor classifications; FundFlow stores source-reported categories instead of
  re-labelling them to mimic the vendor.
- Exchange and MIC values describe the vendor's dissemination convention; FundFlow
  returns them only where a source records them.
- Vendor NAV timing and precision can differ from an issuer NAV by fractions of a
  cent even when the economic value agrees.
- ABSOLUTE return, yield, minimum-investment, sustainability and brokerage fields
  require a publisher that actually states them. FundFlow leaves them null rather
  than inferring them.


## US production research update — 2026-11-15

### What exact parity requires

Twelve Data's documented mutual-fund product includes a daily-updated directory, price history, and separate summary, performance, risk, ratings, composition, purchase-info, and sustainability endpoints. The directory is documented at 1 credit per request; the full-data and several premium sections are documented at 200–1,000 credits and are plan-gated. Identical JSON keys are an interface-compatibility goal; identical values require the same source, instrument/share class, calculation method, currency, and as-of date.

Twelve Data's current [Terms of Use](https://twelvedata.com/terms) restrict external redistribution unless the subscription tier/add-on or a separate written agreement expressly allows it, and include a restriction on using the platform to build a competing product. FundFlow's stated plan is to compete in fund data. Therefore, Twelve Data must not be used as a production ingestion source or copied into customer responses unless the company receives written authorization covering competitive use, storage/caching, derived metrics, and customer API redistribution. Comparison access and customer redistribution are separate use cases. Scraping Twelve Data pages or API responses to populate FundFlow is not an alternative authorization path.

### US source coverage and publication cadence

| Data | Best verified source route | Update/coverage constraint | FundFlow implication |
|---|---|---|---|
| Fund/series/share-class identity | [SEC Investment Company Series and Class Information](https://www.sec.gov/data-research/sec-markets-data/investment-company-series-class-information) | SEC identifiers include series/class IDs and optional filer-supplied ticker; the report also includes products that have not started selling or have ceased but are not marked inactive. It is not a complete closed-end fund/UIT catalog. | Treat CIK/series/class as regulatory identity, preserve ticker as optional, and build explicit active/public-sale status instead of equating every SEC row with a currently purchasable fund. |
| Daily mutual-fund NAV | Issuer/fund administrator NAV feeds or a contractually licensed market-data vendor; supported direct adapters currently cover only selected issuers | SEC N-PORT is not a general daily NAV service. Money-market NAV data comes through a different filing/feed. Public issuer sites have inconsistent formats and terms. | Continue source-specific adapters and measure per-issuer coverage. Do not present Yahoo-derived values as official NAV. Do not synthesize daily open/high/low from a single mutual-fund NAV; expose it as a NAV observation/close basis. |
| Non-money-market portfolio holdings | [SEC Form N-PORT data sets](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets) and SEC filing submissions | Bulk structured archives update quarterly. Filings describe monthly month-end schedules but public availability is delayed; current SEC materials say the rule changes that would accelerate public availability were delayed to November 17, 2027. N-PORT excludes money-market funds and SBICs, and not every product/class maps cleanly to an SEC series. | Store report period, filing/accession, retrieval time, and series-level scope. Holdings are not a daily field; expose age/freshness and “latest disclosed report date.” Never copy series holdings into a share class without documenting the inherited series scope. |
| Money-market holdings and daily class NAV | [SEC Form N-MFP monthly data sets](https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets) | Monthly report; filings are due by the fifth business day and public archives update monthly. The archive includes daily class NAV fields and portfolio schedules. | Refresh monthly after publication, not by downloading every historical archive daily. Maintain month/report-date lineage. |
| Fees, prospectus, objectives, distributions, minimums | SEC filings and issuer fund pages/documents | Definitions and effective dates vary by share class; broker availability and minimums can change or be distribution-channel-specific. | Add only fields that can be tied to the exact class and source date; preserve gross/net fee distinction and link prospectus. |
| Performance | Official issuer returns or a licensed source; computed total returns require dated distributions plus NAV | NAV-only change is price return, not necessarily total return; load-adjusted and category returns have vendor-specific methods. | Do not label calculated NAV changes as vendor total return without distributions and documented methodology. Keep source-reported and FundFlow-calculated metrics distinct. |
| Risk / ratings / peer ranks | Licensed analytics provider or explicitly disclosed FundFlow calculation | Twelve Data's grades and peer metrics are provider methodologies. Raw filings do not provide comparable 0–5 fund ratings. | Do not map arbitrary SEC or issuer risk fields to Twelve Data ratings. If calculated internally, version formulas and label results as FundFlow metrics. |
| Composition / sectors / asset allocation | SEC N-PORT position files plus a maintained security master; issuer-reported composition | Raw positions need security classification, cash/derivative treatment, denominator, class/series mapping, and report dates. Vendor sector weights can differ by classification rules. | Keep filed positions as primary facts; publish calculated sector/asset aggregates with methodology and coverage, separately from issuer/vendor-provided composition. |
| ESG/sustainability | Issuer statements and licensed ESG providers | No single public official dataset supplies comparable fund-level ESG scores and corporate coverage for the entire US universe. | Return unavailable unless a source publishes the value; do not infer an ESG score from prospectus wording. |

Sources: [SEC Form N-PORT](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets), [SEC Form N-MFP](https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets), [SEC series/class report](https://www.sec.gov/data-research/sec-markets-data/investment-company-series-class-information), [SEC delayed N-PORT rule amendments](https://www.sec.gov/rules-regulations/2025/04/s7-26-22), [Twelve Data mutual-fund API docs](https://twelvedata.com/docs/mutual-funds), and [Twelve Data usage terms](https://twelvedata.com/terms).

### Current universe and coverage boundary

The currently loaded **39,139 US-domiciled records** are not automatically 39,139 active, publicly purchasable mutual funds: the universe can include ETFs, share classes, insurance separate accounts, unlaunched products, stale/inactive registrations, and other SEC series. A production coverage denominator must first be defined (active vs. liquidated, registered open-end mutual fund vs. ETF/MMF, public-sale eligibility, and class vs. series). The live API coverage snapshot checked on 2026-11-14 showed 25,685 records with NAV, 33,364 with holdings, and 25,267 with both; these are availability flags, not proof of current freshness or exact source comparability.

It is not technically supportable to promise that every one of those records will always have a fresh NAV and portfolio: some are inactive/non-public, issuer coverage is fragmented, and portfolio disclosures have legal publication lags. A client-facing contract should make freshness observable per field (valuation/report date, retrieved-at time, source, and age), distinguish “not published,” “not mapped,” “temporarily delayed,” and “source unavailable,” and enforce explicit stale-data thresholds.

### Workflow cadence correction

The daily workflow must not repeatedly download the 400+ MB N-PORT bulk archive or replay older quarters. Daily ingestion now handles source connectors, current NAV refresh, recent EDGAR filings, and selected issuer feeds. Dedicated workflows run the latest N-MFP archive monthly and the latest safely published N-PORT archive plus prior-quarter gap recovery quarterly. This aligns ingestion frequency with the provider's publication schedule; it cannot make holdings updates daily.

Before public launch, the company must also settle data licensing/redistribution rights for every non-public-domain vendor feed, validate API key rotation and secret storage, and publish endpoint-level coverage/freshness SLAs. These are launch gates, not fields that ETL code can resolve by itself.
