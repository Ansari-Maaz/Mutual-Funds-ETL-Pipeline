# Official enrichment of portfolio-holding fields

The fund-profile holdings table shows the fields that the SEC actually files
and, separately, a small number of values that FundFlow derives from consecutive
SEC filings. No Twelve Data value and no third-party security-price or estimate
feed is read or written. Every value below is either filed by the fund or a
deterministic function of filed values, and the API returns the calculation basis
with each derived metric.

## Fields that were being dropped from the N-PORT filing

The SEC DERA `FUND_REPORTED_HOLDING.tsv` publishes 22 columns. The original
import stored only name, CUSIP, balance, value, weight and asset category. The
following filed columns are now stored on `portfolio_holdings` verbatim:

| TSV column | Stored column | Notes |
| --- | --- | --- |
| `UNIT` | `unit` | `NS` shares, `PA` principal, `NC` contracts, `OU` other |
| `ISSUER_LEI` | `issuer_lei` | Filed legal-entity identifier |
| `ISSUER_TYPE` | `issuer_type` | `CORP`, `MUN`, `UST`, `RF`, … |
| `INVESTMENT_COUNTRY` | `investment_country` | ISO country of the issuer |
| `IS_RESTRICTED_SECURITY` | `is_restricted` | Y/N converted to boolean |
| `FAIR_VALUE_LEVEL` | `fair_value_level` | Filed 1/2/3 hierarchy level |
| `DERIVATIVE_CAT` | `derivative_category` | `FUT`, `SWP`, `OPT`, … |
| `PAYOFF_PROFILE` | `payoff_profile` | Filed long/short profile |
| `EXCHANGE_RATE` | `exchange_rate` | Filed conversion rate |

`ASSET_CAT` was already summed into the `asset_allocation` snapshot; the
per-position code is now also retained as `asset_category`.

## Ticker and ISIN crosswalk

A single N-PORT filer usually reports only one of CUSIP/ISIN/ticker for a
position. In the 2026q3 archive only 11.8% of positions carry a ticker row, but
the same CUSIP is held by many funds: 60,332 distinct CUSIPs have a ticker
reported somewhere in the filing population, covering 72.8% of positions that
have a CUSIP.

`sync-sec-nport-identifiers` builds `security_identifier_map` from every filing
in each extracted quarterly archive. A CUSIP is assigned a ticker or ISIN only
when one value has at least 80% of the filed identifier votes; disputed values
stay null. Placeholder CUSIPs (`000000000`, `999999999`) are ignored. The map
is then applied to every holding row whose ticker/ISIN is empty. A first pass
from the 2026q3 archive filled 5,467,031 holding tickers and 21,017 ISINs;
coverage rose from 13% to 50.6% of all stored positions.

## Sector (issuer industry)

Form N-PORT has no sector field. The only official issuer-industry
classification the SEC publishes is the Standard Industrial Classification code
in each registrant's EDGAR submission. `sync-sec-industry`:

1. reads `company_tickers_exchange.json` (ticker → CIK),
2. reads `data.sec.gov/submissions/CIK##########.json` once per CIK, paced below
   the SEC's request guidance,
3. stores `ticker`, `cik`, `sic`, `sic_description` and a grouped sector label in
   `security_industry`.

The sector label groups official SIC major groups into familiar sectors and
keeps the exact SIC code/description in the API response and in each metric's
`calculation_basis`, so the classification is auditable. A holding with no
ticker match keeps a null sector; its filed `asset_category` and `issuer_type`
are still shown.

## Derived metrics (`holding_metrics`)

`sync-sec-nport-metrics` computes these from the positions themselves:

| Field | Definition | Basis |
| --- | --- | --- |
| `first_bought_date` | Earliest N-PORT report period for the same fund/security in the imported archive window | Lower bound if the position predates the window |
| `share_change_percentage` | Quantity versus the fund's immediately preceding N-PORT report, same security and unit | No value when the position is new or the unit changed |
| `one_year_return` | Change in filed market value per share/principal between report periods about 12 months apart | Excludes distributions; not split-adjusted; implausible values outside -95%…+500% are rejected |
| `sector` | SEC SIC sector from `security_industry` via the filed ticker | SIC code and description retained |

`forward_pe` is deliberately never written: no official U.S. source publishes a
forward earnings estimate for an individual portfolio holding. The UI omits the
column instead of showing an empty field.

A **trailing P/E** is available from two filed facts and is stored separately in
`holding_metrics.trailing_pe` by `sync-sec-eps` followed by
`sync-sec-trailing-pe`:

1. the N-PORT filed market value divided by the filed balance gives the price
   paid for one share (or one unit of principal);
2. the issuer's SEC XBRL `EarningsPerShareDiluted` company concept gives the
   newest annual diluted EPS (10-K/20-F/40-F, annual duration only, cached in
   `data/raw/united_states/companyconcept`).

`security_fundamentals` keeps one EPS fact per ticker with its CIK, fiscal-year
end, filing date and XBRL URL; each P/E row records that EPS value and period in
`trailing_pe_basis`. Negative-EPS issuers, non-common-equity positions and
ratios outside 0.1×–1000× are rejected. This is a filed-price/ filed-earnings
ratio, not a forecast and not a vendor estimate.

## Source precedence and idempotency

- Filed values always win; the crosswalk only fills empty identifiers and never
  overwrites a value reported by the fund itself.
- Re-importing a quarter replaces that fund/report-date's rows with the filed
  values, so the enrichment can be replayed without duplicates.
- Re-running the identifier, industry or metrics sync updates existing rows via
  `ON CONFLICT`, keeping the run reproducible.

## Individual N-PORT filings

The 540,050 rows written by the older `sync-sec-holdings` path predate the
Item C.4 columns. `scripts/backfill_nport_filing_fields.py --download --apply`
re-parses those SEC submission texts (the CIK comes from each row's recorded
`source_url`, not from the accession prefix), verifies that the filing's series
matches the mapped funds, and fills the ten official attributes in one bulk
update. Reports without a local cache are downloaded once and kept in
`data/raw/united_states/nport_filings`.

## Commands

```bash
./.venv/bin/python -m app.cli sync-sec-nport-bulk --quarter 2026q3
./.venv/bin/python -m app.cli sync-sec-nport-identifiers --no-rebuild --latest-only
./.venv/bin/python -m app.cli sync-sec-industry --latest-holdings # SEC EDGAR SIC resolver
./.venv/bin/python -m app.cli sync-sec-nport-metrics             # derived metrics
./.venv/bin/python -m app.cli sync-sec-eps                       # SEC XBRL annual EPS
./.venv/bin/python -m app.cli sync-sec-trailing-pe               # trailing P/E per position
./.venv/bin/python scripts/backfill_nport_filing_fields.py --download --apply
./.venv/bin/python scripts/backfill_holding_sector.py             # refresh sectors after new CIKs
```

The latest-report identifier apply keeps the initial bulk fill from rewriting
millions of historical rows: only each fund's newest report is updated. When
new SIC mappings arrive later, `backfill_holding_sector.py` refreshes only the
sector and its stated basis on the newest metric rows, avoiding a second full
metrics rebuild.

Alongside holdings, the cached SEC archives also feed source-backed profile
snapshots: N-PORT `nport_financials`, N-MFP `nmfp_class_financials`, N-CEN
`financials`/`registrant`/`etf_profile`, and N-1A `fees`/bar-chart
`performance`/`yields`. See `docs/US_OFFICIAL_SOURCES.md` for the filed basis of
each dataset.
