# Refreshing U.S. NAV and holdings data

## NAV history

`scripts/refresh_us_nasdaq_nav_history.py` fetches reported daily close/NAV values from the Nasdaq Fund Network quote history for explicitly selected SEC-linked U.S. mutual-fund share classes. It inserts only missing `(fund, date, currency)` observations. Existing FundFlow values are preserved; same-date differences are included in the run report for review.

Example for the ten symbols used in the Twelve Data sample comparison:

```bash
./.venv/bin/python scripts/refresh_us_nasdaq_nav_history.py \
  --ticker VFIAX --ticker VTSAX --ticker FXAIX --ticker SWPPX \
  --ticker FCNTX --ticker DODGX --ticker FBALX --ticker VWELX \
  --ticker VBTLX --ticker VTIAX --history-days 365
```

The run writes a JSON report under `reports/`. Nasdaq's Fund Network specification describes daily mutual-fund NAV dissemination, but this public quote endpoint is not a formally versioned API and can change. The import uses the response's unadjusted `close` field, not adjusted close or inferred OHLC values. Source URLs are stored with the rows.

## SEC portfolio holdings

The existing `sync-sec-holdings` command loads N-PORT positions and report dates from SEC EDGAR. A normal rolling refresh is:

```bash
./.venv/bin/python -m app.cli sync-sec-holdings --history-days 450
```

For a smaller latest-report refresh, add `--latest-only`. SEC N-PORT covers eligible registered funds other than money-market funds and publishes filings after their report periods; it does not cover every U.S. fund product or provide real-time positions. The source accession and report date remain attached to holdings.

## SEC N-PORT quarterly bulk holdings

`sync-sec-holdings` walks individual EDGAR filings for matched series. The DERA
quarterly bulk data set is faster and more complete for whole-universe refreshes:

```bash
./.venv/bin/python -m app.cli sync-sec-nport-bulk
./.venv/bin/python -m app.cli sync-sec-nport-bulk --quarter 2026q2 --only-missing
```

The default quarter is the newest one that is safely published (45-day lag, and
never a quarter that has not ended). Replaying older quarters with `--only-missing`
recovers the last official holdings for series absent from the newest quarter.
This bulk import belongs on the quarterly workflow, not the daily run: SEC posts
the public structured data quarterly, and public holdings are delayed. The
individual-filing `sync-sec-holdings` command remains part of the daily refresh.
See [US_OFFICIAL_SOURCES.md](US_OFFICIAL_SOURCES.md) for the full source list and
coverage reporting commands.

## SEC N-MFP money-market bulk holdings

Money-market funds report holdings on Form N-MFP, not N-PORT. Import the monthly
bulk data set to get their positions, adviser/administrator names, and (optionally)
class NAV:

```bash
./.venv/bin/python -m app.cli sync-sec-nmfp-bulk --months 1 --all --assign-usd-nav
```

Only the newest report date per series is imported. The monthly workflow runs this
command for the latest archive only; use a larger `--months` value for an explicit
backfill. The SEC daily NAV table has no
currency column; `--assign-usd-nav` writes USD observations for U.S. domiciled
funds and records the accession as provenance. Without the flag, holdings and
profile fields are still imported but no canonical NAV rows are written.

## SEC N-CEN profile and service-provider bulk data

N-CEN is the annual census filing for each registered fund. The quarterly DERA
archive fills official profile fields that N-PORT and N-MFP do not carry:

```bash
./.venv/bin/python -m app.cli sync-sec-ncen-bulk --quarters 8
```

It stores the series-level NAV/market-price snapshot, advisory fee and net
operating-expense percentages, average net assets, adviser (with start date),
administrator, custodian, transfer agent, pricing service, public accountant,
principal underwriter, and classification flags. The newest report-ending period
per series wins, so overlapping quarters are safe. A canonical NAV row is written
only for series that map to a single local share class; multi-class series keep the
figure in the `nav_snapshot` profile with its series scope.

## SEC prospectus risk/return and tailored shareholder report facts

Two official SEC sources fill class-level fees, returns, objective, strategy and
inception date. Both are keyed by SEC class ID (`C000…`), so they join directly to
`funds.source_fund_id`:

```bash
./.venv/bin/python -m app.cli sync-sec-rr-profiles --quarters 4
./.venv/bin/python -m app.cli sync-sec-ncsr-tsr --since-days 45 --workers 8
```

- `sync-sec-rr-profiles` reads the DERA prospectus risk/return ZIPs: net/gross
  expense ratios and their components, portfolio turnover, 1/3/5/10-year average
  annual returns, objective and strategy text, and `PerfInceptionDate`. Benchmark
  index rows and load-adjusted variants are skipped. `--quarters 60` replays every
  published archive; `--dry-run` reports counts without writing.
- `sync-sec-ncsr-tsr` reads the Tailored Shareholder Report XBRL in N-CSR/N-CSRS
  filings for net expense ratio, net assets, holdings count, turnover, ticker,
  inception date, average annual returns and industry-sector weights. The newest
  annual and semi-annual filings are merged field by field. Use `--only-gaps` for a
  one-time backfill of empty ticker/inception/net-asset fields and the default
  rolling window for the daily refresh.
- Both fill a fund field only when it is empty, and every value keeps its
  accession number and report date in `fund_profile_snapshots`.
- Some issuers publish one `TradingSymbol` for every class in a series (for
  example Davis Government Money Market Fund reports `RPGXX` on its Class A, C
  and Y contexts). That value is stored as filed; the API answers a ticker lookup
  that matches more than one class with HTTP 409 and asks for ISIN or CUSIP.

## Reference-field gaps (ticker, ISIN, category, inception, manager, AUM)

`scripts/audit_us_field_gaps.py` writes a per-fund worklist with the official
source that can supply each missing value:

```bash
./.venv/bin/python scripts/audit_us_field_gaps.py
```

It produces `reports/us_field_gaps.csv`, `reports/us_field_gaps_summary.json` and
`reports/us_field_gaps_summary.md`. The standard enrichment pass fills them from
official data:

```bash
./.venv/bin/python -m app.cli enrich-us-funds --tickers --isins --net-assets --vanguard --issuer-navs --no-audit
```

- `--tickers` reads SEC's live `company_tickers_mf.json` (class ID to ticker).
- `--isins` only assigns an ISIN backed by a validated CUSIP/ISIN pair in N-PORT
  holdings; US fund classes that never appear as another fund's holding stay null.
- `--vanguard` syncs the Vanguard all-products directory (inception, expense ratio,
  category where published).
- `--net-assets` reads the newest N-PORT bulk quarter.
- Inception dates and tickers left empty after that pass are covered by
  `sync-sec-rr-profiles` and `sync-sec-ncsr-tsr`; a class is only given a ticker
  that no other U.S. class already uses.

`category` stays null unless an issuer publishes one. No official source publishes
a Morningstar/Lipper-style style category; N-CEN vehicle/strategy flags are exposed
separately as `classification` in the API and are never written to `category`.

The fund loader preserves existing enrichment values when a connector refresh
sends null for a field it does not own, so identity-only refreshes cannot erase
tickers, ISINs, inception dates, managers or net assets.

## Official issuer NAV adapters

Vanguard, SSGA/SPDR, Capital Group/American Funds and GraniteShares publish dated
NAV on their own sites. Run them with:

```bash
./.venv/bin/python -m app.cli enrich-us-funds --issuer-navs-missing --no-audit
```

`--issuer-navs-missing` asks only for funds with no stored NAV observation; use
`--issuer-navs` for a full refresh of every issuer-covered class.

Adapters validate the ticker in the payload and store the source URL with every
observation. Issuer sites that block automation or render NAV only in JavaScript
are left uncovered.

### Nasdaq Fund Network fallback for ticker-bearing classes

Classes that have a SEC ticker but still no NAV can be requested from Nasdaq's
Fund Network, then loaded by the SEC connector:

```bash
./.venv/bin/python scripts/refresh_us_nasdaq_navs.py --missing-nav --delay 0.35
./.venv/bin/python -m app.cli run --source sec_open_end_fund_classes
```

`--missing-nav` selects only funds with no stored NAV observation. Funds without
a ticker are not requested, because there is no official symbol to query.

## Per-country freshness report

```bash
./.venv/bin/python scripts/report_country_freshness.py \
  --markdown reports/country_freshness.md --json reports/country_freshness.json
```

It lists, for every domicile country, the fund count, how many funds have a NAV
or holdings, and the newest stored date for each.

## Twelve Data comparison

After refreshing official-source data, compare the same tickers and valuation dates using `scripts/compare_twelvedata_universe.py`. The comparator records provider coverage and field differences; it does not write Twelve Data values into FundFlow. A vendor close and an official mutual-fund NAV can differ in precision, valuation timing, or data basis. Keep raw mismatches visible instead of editing FundFlow to force a parity result.

Use a current Twelve Data API key from a private environment variable or the script's hidden prompt. Do not commit API keys or copy them into `.env.example`.
