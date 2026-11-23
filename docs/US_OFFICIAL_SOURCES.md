# Official U.S. NAV, holdings and fund-detail sources

This page records which official U.S. sources FundFlow imports, the commands that
run them, and the gaps that remain. Only official sources are used for U.S. NAV and
portfolio holdings. A field that the official source does not publish stays null
rather than being filled from a third-party feed.

## Imported sources

| Source | Type | What is imported | Command |
| --- | --- | --- | --- |
| SEC Form N-PORT quarterly DERA bulk data set | Regulator bulk archive | Portfolio positions, net assets, report dates, security identifiers | `python -m app.cli sync-sec-nport-bulk` |
| SEC N-PORT filings (EDGAR) | Regulator filings | Per-filing holdings for selected/matched series | `python -m app.cli sync-sec-holdings` |
| SEC Form N-MFP | Regulator filings | Money-market class NAV history snapshot (currency unassigned) | `python -m app.cli sync-sec-nmfp` |
| SEC Form N-MFP monthly bulk data sets | Regulator bulk archive | Money-market portfolio holdings, adviser/administrator, class daily NAV | `python -m app.cli sync-sec-nmfp-bulk` |
| SEC Form N-CSR/N-CSRS statement of assets | Regulator filings | Class-level filed period-end NAV for classes without a ticker or daily feed | `python scripts/backfill_ncsr_nav.py` |
| SEC Form N-CSR/N-CSRS schedule of investments | Regulator filings | Filed security names, quantities and market values for series missing from the N-PORT archives | `python scripts/backfill_ncsr_holdings.py` |
| SEC individual N-MFP filings | Regulator filings | Money-market holdings and daily class NAV for series absent from the monthly bulk archive | `python scripts/backfill_nmfp_individual.py --assign-usd-nav` |
| SEC Form N-CEN quarterly bulk data sets | Regulator bulk archive | NAV/market price per share at period end, advisory fee and net expense ratios, average net assets, adviser and start date, administrator, custodian, transfer agent, pricing service, public accountant, underwriter, classification flags, and the Item C.2 class ticker table | `python -m app.cli sync-sec-ncen-bulk` |
| SEC N-CEN / N-PORT / N-MFP reporting evidence | Regulator bulk archive | `filing_status` snapshot: whether the series still reports, newest report date per form | `python -m app.cli sync-sec-filing-status` |
| SEC N-1A prospectus narrative (485/497 primary documents) | Regulator filings | Share-class inception date when the filing states a full commencement date for the named class | `python -m app.cli sync-sec-n1a-inception` |
| Vanguard product pages | Asset manager | Dated NAV, inception date, expense ratio, category where published | `python -m app.cli enrich-us-funds --issuer-navs` |
| SSGA / SPDR NAV workbooks | Asset manager | Dated NAV, shares outstanding, net assets | `python -m app.cli enrich-us-funds --issuer-navs` |
| Capital Group / American Funds product pages | Asset manager | Current daily NAV for retail share classes | `python -m app.cli enrich-us-funds --issuer-navs` |
| GraniteShares NAV history endpoint | Asset manager | Daily NAV and AUM history from the signed per-product endpoint | `python -m app.cli enrich-us-funds --issuer-navs` |

The enrichment commands also fill fund details from official data:
`--net-assets` (N-PORT AUM), `--tickers` (live SEC series/class endpoint),
`--isins` (validated N-PORT security identifiers) and `--vanguard` (Vanguard
directory profiles).

## SEC portfolio-holding enrichment

The filing's full Item C.4 payload, the official CUSIP→ticker/ISIN crosswalk,
the SEC EDGAR SIC industry map and the metrics derived from consecutive filings
are documented in [HOLDINGS_ENRICHMENT.md](HOLDINGS_ENRICHMENT.md). The relevant
commands are `sync-sec-nport-identifiers`, `sync-sec-industry`,
`sync-sec-nport-metrics`, `sync-sec-eps` and `sync-sec-trailing-pe`.
`sync-sec-eps` reads the issuer's SEC XBRL `EarningsPerShareDiluted` company
concept (10-K/20-F/40-F annual facts) into `security_fundamentals`;
`sync-sec-trailing-pe` divides the N-PORT filed price per share by that EPS and
stores the ratio with its EPS period and XBRL URL. No sector, forward P/E or
first-purchase date is invented: an unsupported field stays empty or is labelled
with its derivation.

## SEC N-PORT bulk holdings

```bash
python -m app.cli sync-sec-nport-bulk                       # newest safely published quarter
python -m app.cli sync-sec-nport-bulk --quarter 2026q2 --only-missing
python -m app.cli sync-sec-nport-bulk --refresh             # re-download the archive
```

- `latest_quarter()` subtracts a 45-day publication lag and never selects a quarter
  that has not ended.
- The archive is downloaded once under `data/raw/united_states/nport_bulk/<quarter>/`
  and loaded through PostgreSQL `COPY` staging tables.
- `PERCENTAGE` in the DERA dataset is already a percentage of net assets, the same
  convention as `portfolio_holdings.portfolio_weight`, so it is stored as filed.
- A holding can have an ISIN row and a ticker row, so identifiers are aggregated
  per `HOLDING_ID` before joining; a direct join would duplicate positions.
- Series-level holdings are duplicated across the series' matched share classes so
  that every class row can show the same reported portfolio.
- The remaining `FUND_REPORTED_INFO` statement fields (assets, liabilities,
  borrowings, cash, credit-spread ranges and three months of gains/flows) are
  imported as a `nport_financials` snapshot by
  `python scripts/import_nport_financial_snapshots.py`. It reads cached archives
  only, keeps the newest report per series and never rewrites holdings or core
  fund columns. Values are series-level and in USD.
- The DERA archive exists from **2019q4** onward. Older quarters
  (`--quarter 2019q4 … 2024q3 --only-missing --no-apply-identifiers`) recover the
  newest official filing for funds whose series stopped reporting before the
  newer bulk archives. `scripts/backfill_missing_nport_holdings.py` is the
  individual-filing fallback for any series still without positions.
- The filed `ASSET_CAT` value of every position is summed per category into an
  `asset_allocation` snapshot (`alloc` values as percentages of net assets). This is
  the official basis for the composition endpoint's asset allocation; derivatives
  are reported at notional and can exceed 100%.
- Identifier columns are normalised: filed `N/A`/`NA`/`NONE` placeholders become
  NULL, and an ISIN is stored only when it matches the 12-character pattern and
  passes the Luhn check digit. A fund ISIN is still only copied to `funds.isin`
  when a filing pairs it with the same CUSIP.
- The import is idempotent per fund and report date: re-running a quarter replaces
  that fund's rows with the official filing values.
- `--only-missing` restricts work to funds with no stored holdings. Replaying older
  quarters this way recovers the last official holdings for series that did not
  report in the newest quarter.

## SEC reporting status

```bash
python -m app.cli sync-sec-filing-status --months 12
```

- Reads the N-CEN, N-PORT and N-MFP bulk archives already on disk and records the
  newest report date per series for each form.
- A series counts as reporting when any filing lands inside the window measured
  back from the newest archive report date (not the wall clock, because the
  archives lag publication).
- Dormant registrations are not deleted and not marked terminated: absence is
  stated as "no filing in the window". N-MFP `FINALFILINGFLAG` is kept as explicit
  termination evidence when a money-market series files its last report.
- The observation is exposed per fund as the API `reporting` object and on
  `GET /api/v1/coverage/us` as `fields.reporting` / `fields.dormant`.

## Official issuer NAV adapters

`app/holdings/us_issuer_nav.py` contains one adapter per issuer. Each adapter:

- selects U.S. funds by provider pattern that have a ticker and no NAV;
- fetches the issuer's own page or workbook and validates the ticker in the payload;
- stores dated NAV observations with `source_id` and `source_url` provenance;
- records per-ticker failures in the run result instead of guessing values.

Run a single adapter:

```bash
python - <<'PY'
from app.holdings.us_issuer_nav import sync_official_us_navs
print(sync_official_us_navs(["graniteshares"], only_missing=True, limit=5))
PY
```

GraniteShares pages embed a signed NAV-history URL. The adapter resolves that URL
at request time per ticker and stores only the most recent `history_days` rows
because the endpoint returns the full product history.

## SEC N-MFP monthly bulk holdings

Money-market funds file Form N-MFP instead of N-PORT, so their holdings come from
the SEC's monthly N-MFP bulk data set rather than the N-PORT archive.

```bash
python -m app.cli sync-sec-nmfp-bulk                                  # newest month, missing holdings only
python -m app.cli sync-sec-nmfp-bulk --all --assign-usd-nav           # refresh holdings + USD class NAV
python -m app.cli sync-sec-nmfp-bulk --months 6 --refresh             # scan six months, re-download
```

- The archive is discovered from the official DERA download page and cached under
  `data/raw/united_states/nmfp_bulk/`.
- Only the newest report date per SEC series across the downloaded archives is
  imported, so loading several months does not duplicate snapshots.
- `NMFP_SCHPORTFOLIOSECURITIES` supplies positions. Its percentage field is a
  fraction of fund net assets and is multiplied by 100 for `portfolio_weight`.
- `NMFP_ADVISER` and `NMFP_ADMINISTRATOR` fill `funds.manager` and
  `funds.administrator` when those fields are empty; money-market funds also get
  `category = "Money market"`.
- The daily class NAV table has no currency column. `--assign-usd-nav` writes
  `currency = "USD"` because every selected fund is U.S. domiciled; without the
  flag no canonical NAV rows are written. The source URL and accession are stored
  with each observation.

## SEC Form N-CEN quarterly bulk data

Form N-CEN is each registered fund's annual census filing. The DERA archive adds
official reference and service-provider data that N-PORT does not carry:

```bash
python -m app.cli sync-sec-ncen-bulk                       # newest 8 quarters
python -m app.cli sync-sec-ncen-bulk --quarters 12 --refresh
python -m app.cli sync-sec-ncen-bulk --no-nav --no-profiles
python -m app.cli sync-sec-ncen-bulk --offline            # cached archives only
```

- The newest report-ending period per SEC series across all scanned quarters is
  used, so running several overlapping quarters never duplicates a snapshot.
- `FUND_REPORTED_INFO` supplies NAV per share, market price per share, advisory
  fee and net operating expenses as percentages of net assets, average net
  assets, index-tracking difference/standard deviation, and classification flags.
- The same table's Item C statement values are stored in a `financials`
  snapshot: total assets, total liabilities, net assets, assets invested, cash,
  borrowings, monthly realized/unrealized gains, monthly sales/reinvestment/
  redemption flows, commissions/principal, and securities-lending income.
- `REGISTRANT` and `REGISTRANT_WEBSITE` supply registrant-level name, file
  number, CIK, LEI, address, phone, website and investment-company type in a
  `registrant` snapshot. These facts describe the fund family, not the adviser.
- `ETF` supplies series-level creation/redemption unit sizes, cash/non-cash
  purchase and redemption percentages and standard deviations, fees, tracking
  difference/standard deviation, and ETF flags in an `etf_profile` snapshot.
- `ADVISER`, `ADMIN`, `CUSTODIAN`, `TRANSFER_AGENT`, `PRICING_SERVICE`,
  `PUBLIC_ACCOUNTANT` and `PRINCIPAL_UNDERWRITER` fill `funds.manager`,
  `funds.administrator` and the `service_providers` snapshot.
- The series-level Legal Entity Identifier (`FUND_REPORTED_INFO.LEI`) is written
  to `fund_identifiers` (`id_type='LEI'`) and to an `identity` profile snapshot.
  The value belongs to the SEC series and is shared by all of its share classes;
  `scripts/backfill_us_series_leis.py` applies the same mapping to cached archives.
- The adviser start date is stored as manager tenure evidence, not as fund
  inception (N-CEN does not report inception).
- Advisory fee and net operating expenses are reported as percentages of net
  assets and stored in `expense_ratio_history` with the basis named. Only a small
  number of closed-end registrants populate these columns; open-end series
  usually leave them blank, so the dataset is not a substitute for prospectus
  expense ratios.
- NAV per share is filed at series level. A canonical USD NAV observation is
  written only when the series maps to exactly one local share class; otherwise
  the value stays in the `nav_snapshot` profile with the series scope recorded.
- Index-tracking figures are labelled as fund-versus-index differences, never as
  absolute fund returns.

## SEC N-MFP class-level facts

Cached N-MFP monthly archives also carry a class-level table with minimum
investment, class net assets and shares outstanding, weekly subscription and
redemption flows, seven-day yield and shareholder composition. Run
`python scripts/import_nmfp_class_snapshots.py` to store the newest filing per
class as an `nmfp_class_financials` snapshot. NAV is never derived from net
assets divided by shares; only values filed as NAV are used as NAV.
`python scripts/backfill_nmfp_nav.py` writes those filed daily class NAVs as
USD `nav_observations`, skipping dates already present for the same class.

## SEC N-1A prospectus risk/return data sets

The SEC DERA "Mutual Fund Prospectus Risk/Return Summary" archives carry the XBRL
facts every open-end fund and ETF files on Form N-1A (`485BPOS`, `497`, `497K`).
They are keyed by SEC class ID (`C000…`), the same value stored in
`funds.source_fund_id`, so no fuzzy matching is involved.

```bash
python -m app.cli sync-sec-rr-profiles --quarters 4 --dry-run
python -m app.cli sync-sec-rr-profiles --quarters 60   # every cached archive
python -m app.cli sync-sec-rr-profiles --offline       # cached archives only
```

- `num.tsv` supplies net/gross expense ratios, management, 12b-1 and other expense
  components, expense examples, portfolio turnover and publisher-reported
  average annual returns (4/12/20/40 quarters → 1/3/5/10 years).
- The same table supplies the rest of the prospectus fee table: maximum sales
  charges, deferred and cumulative sales charges, redemption/exchange fees,
  account fees, fee waivers, acquired-fund fees, breakpoint minimums, and the
  no-redemption expense example. These are stored in a `fees` snapshot with a
  per-field unit and basis; percentage tags are already fractions.
- Prospectus bar-chart highest/lowest quarterly and year-to-date returns are
  stored in `performance`, and money-market 7-day/30-day yields in `yields`.
  Bar-chart and yield rows without a class dimension are skipped when a filing
  contains several unattributable values.
- A value that appears twice for the same class/date/document with different
  values is marked ambiguous and is not imported.
- Benchmark-index rows (`IndexAxis`, `IndustrySectorAxis`) and sales-load variants
  other than `WithoutSalesLoad` are skipped, so a category or index return is
  never written as the class return.
- `txt.tsv` supplies `PerfInceptionDate`, `AnnualReturnInceptionDate`,
  `dei:TradingSymbol`, the objective and strategy text blocks, and `scn.tsv` the
  cover-page class/ticker table.
- Snapshots: `inception_date`, `summary` (fees, turnover, objective, strategy,
  share-class inception), `expense_ratio_history`, `performance`, `fees`,
  `yields` and `n1a_prospectus`. Each keeps the accession number and report
  period.
- Only empty `funds.inception_date`/`funds.ticker` rows are filled, and a ticker is
  assigned only when no other U.S. class already owns it.

## SEC N-CSR statement-of-assets NAV recovery

`scripts/backfill_ncsr_nav.py` reads the latest annual/semi-annual report for each
registrant that still has share classes with no NAV observation. The Statement of
Assets and Liabilities files `Net asset value per share` for each class; the
script parses four official layouts (single-row class labels, a NAV section with
class rows, a Class/Net-asset-value column table, and the "offering and
redemption price per share" sentence). The series name is resolved from the
filing text immediately before the statement and mapped through the `summary`
snapshot. Only positive filed NAVs are written, with the report date and SEC
URL as `sec_ncsr_nav` observations; existing NAV rows are never changed.

## SEC N-CSR schedule-of-investments holdings

`scripts/backfill_ncsr_holdings.py` targets US classes that still have no
portfolio holdings. It selects tables with a filed `Value` column and a
`Shares` or `Principal amount` column, resolves the series from the filing text,
and attaches the filed rows to every target share class of that series. Values
filed under a `Value (000)` heading are converted with the stated thousands unit;
principal amounts in thousands are not published as a quantity. All rows carry
`data_source='sec_ncsr_holdings'`, the report date and the SEC URL, and conflicts
with existing holdings are skipped.

## SEC individual N-MFP filings

`scripts/backfill_nmfp_individual.py` inspects the newest individual N-MFP family
filings for registrants with missing NAV or holdings. It matches the filed
`seriesId`/`classesId` to local funds, imports
`scheduleOfPortfolioSecuritiesInfo` rows with filed CUSIP/ISIN, market value and
net-asset percentage, and can write the filed daily class NAV history when
`--assign-usd-nav` is explicitly passed (the filing does not state a currency).
Use `--max-filings` to expand the search when a series stopped filing recently.

## SEC tailored shareholder reports (N-CSR / N-CSRS)

Since 2024 every registered fund files a machine-readable Tailored Shareholder
Report. It is the most current official source for class-level fees, returns and
sector weights.

```bash
python -m app.cli sync-sec-ncsr-tsr --since-days 45 --workers 8
python -m app.cli sync-sec-ncsr-tsr --only-gaps --workers 8 --batch-size 100
```

- Facts are read only inside `oef:ClassAxis` contexts, so values are attributable
  to a `C000…` class.
- `ExpenseRatioPct`, `AssetsNet`, `HoldingsCount`,
  `InvestmentCompanyPortfolioTurnover`, `TradingSymbol`, `PerfInceptionDate`,
  `ClassName` and `FundName` are imported as scalar facts; `AvgAnnlRtrPct` and
  `PctOfNav` as period/fact lists.
- The newest annual and semi-annual filings are merged field by field: newer
  scalars win, while returns that only the annual report carries are retained.
  For a period filed twice, the explicit `WithoutSalesLoad` value is kept.
- `ExpenseRatioPct` is a fraction of net assets and `PctOfNav` a fraction; both are
  stored with the fraction and the derived percent, never silently rescaled.
- Sector members are reduced to a readable label: the taxonomy wrappers
  (`Sector…Sector`, `Industry…Sector`) are stripped, acronyms such as `REITs` are
  kept, and filer allocation buckets (`Other Sectors`,
  `Cash and Cash Equivalents Sector Weighting`, `Bond Equity Sector …`),
  benchmark ids, totals, `…Minus…` members and CUSIP-coded members are dropped.
  A snapshot is deleted when nothing but such buckets was filed.
- `AssetsNet` is series-level net assets repeated on every class context. It is
  written to `funds.net_assets` only when that field is empty, and the payload
  records `net_assets_scope` so the series scope is never lost.

## Daily pipeline

`.github/workflows/etl.yml` runs, in order:

1. `sync-sec-holdings` — per-filing holdings refresh.
2. `sync-sec-nport-bulk` — newest N-PORT quarter.
3. `sync-sec-nport-bulk --quarter <previous> --only-missing` — backfill for series
   absent from the newest quarter.
4. `sync-sec-nmfp-bulk --all --assign-usd-nav` — money-market holdings and NAV.
5. `sync-sec-ncen-bulk --quarters 4` — annual census profiles, fees, AUM and classification.
6. `sync-sec-rr-profiles --quarters 4` — prospectus fees, turnover, returns, objective, strategy, inception and ticker.
7. `sync-sec-ncsr-tsr --since-days 45 --workers 8` — tailored shareholder report fees, returns and sector weights.
8. `enrich-us-funds --tickers --isins --net-assets --vanguard --issuer-navs-missing --no-audit` — AUM, identifiers and issuer NAV gaps.
9. `scripts/backfill_us_isins_from_sec_holdings.py --apply` — validated ISIN evidence.
10. `scripts/audit_us_field_gaps.py` — reference-field worklist.
11. `audit-us-coverage` and `scripts/report_country_freshness.py` — coverage and per-country freshness reports.

## Coverage reporting

```bash
python -m app.cli audit-us-coverage          # reports/us_fund_coverage_audit.*
python scripts/audit_us_fund_gaps.py         # reports/us_fund_gaps.*
python scripts/audit_us_field_gaps.py        # reports/us_field_gaps.*
python scripts/report_country_freshness.py   # reports/country_freshness.*
```

Field-by-field research and the reason each remaining value is not importable from
an official source: [US_FIELD_GAP_RESEARCH.md](US_FIELD_GAP_RESEARCH.md).

The API exposes the same view at `GET /api/v1/coverage/us`, and the console shows it
under **US coverage**. The endpoint returns universe counts, field completeness,
the largest NAV and holdings gaps by provider, and the official U.S. source registry.

## Known gaps

- Money-market funds file N-MFP rather than N-PORT. `sync-sec-nmfp-bulk` imports
  their portfolio schedule, adviser/administrator and (with `--assign-usd-nav`)
  class NAV. The SEC daily NAV rows do not state currency, so USD is assigned only
  as an explicit, documented option for U.S. domiciled funds.
- Share classes without a ticker (about 9,600 records, mostly variable-insurance
  trusts) have no centralized official daily NAV feed. They remain without NAV
  rather than being matched to another class.
- Series that never filed in the imported N-PORT quarters are inactive, pre-launch,
  or non-N-PORT filers; replaying older quarters is the only official recovery.
- US fund ISINs are not published in SEC N-PORT/N-MFP/N-CEN bulk data (the
  identifier columns describe portfolio securities, not the fund's own class).
  FundFlow only assigns an ISIN when a validated CUSIP/ISIN pair for the same
  ticker appears in filed holdings; classes that never appear as another fund's
  holding stay null.
- The SEC `company_tickers_mf.json` mapping covers 28,628 classes. Classes absent
  from it (mostly variable-insurance trusts, 529 plans and institutional classes)
  have no official ticker, so they remain without one rather than borrowing a
  sibling class's symbol.
- N-CEN is an annual census: it supplies a dated NAV snapshot, not a daily NAV
  series. Fund inception is therefore taken from the N-1A prospectus and tailored
  shareholder report facts instead, and portfolio-manager names remain dependent
  on prospectuses and statements of additional information.
- No official source publishes a Morningstar/Lipper-style investment category.
  N-CEN reports vehicle/strategy flags (ETF, index, money market, target date,
  fund of funds), which the API exposes as `classification` and never as
  `category`. `funds.category` keeps only publisher-reported values.
- Some issuer sites block automation or render NAV only in JavaScript; those are
  recorded as blocked rather than scraped with workarounds:
  Fidelity (temporary-unavailable), John Hancock (403), MassMutual (403),
  Invesco (406), Schwab (404), Nationwide (JS app), Direxion (403),
  Themes/Innovator/ProShares/Tidal (no public NAV in HTML or endpoint).
- Capital Group only exposes retail product pages; 529 classes without one are not
  covered.

When adding a source, register it in `app/catalog.py` with its verification and
integration status so the coverage page and source registry stay consistent.
