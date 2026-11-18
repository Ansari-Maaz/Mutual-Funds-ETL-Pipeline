# U.S. fund missing-field research (official sources only)

Scope: U.S.-domiciled fund records in FundFlow (`funds.domicile_country = 'US'`).
No Twelve Data values are read or written. Every candidate import below is tied
to the official publisher that states the value.

Worklists produced by the read-only audits:

- `reports/us_field_gaps.csv` — one row per US fund with the fields it is missing
  and the official source/action that can fill each one.
- `reports/us_field_gaps_summary.md` — counts by field and the largest providers.
- `reports/us_fund_gaps.csv` — NAV/holdings gap per fund with the official dataset
  that can resolve it.

## Field-by-field findings

| Field | Missing (measured) | Official source checked | What was imported | Why the rest stays null |
| --- | ---: | --- | --- | --- |
| `name` / `legal_name` | 0 | SEC investment-company series/class master | Already complete | — |
| `ticker` | 7,451 | SEC `company_tickers_mf.json`, N-1A prospectus `TradingSymbol` (`scn.tsv`), N-CSR tailored shareholder report `TradingSymbol` | 31,688 present | Classes absent from all three files publish no symbol: variable-insurance separate accounts, 529 plan classes, and institutional classes. Borrowing a sibling class's ticker would be false. |
| `isin` | 38,369 | SEC N-PORT `IDENTIFIERS` (portfolio security CUSIP/ISIN), with pattern and Luhn check-digit validation plus exact ticker/name agreement | 770 classes backed by a validated CUSIP/ISIN pair | The SEC series/class master explicitly has no ISIN. N-PORT identifiers describe portfolio securities, not the filer's own share classes. There is no official bulk US fund-ISIN feed, so a class that is never held by another filer cannot be assigned one. |
| `inception_date` | 22,301 | N-1A prospectus XBRL `PerfInceptionDate`, N-CSR tailored shareholder report `PerfInceptionDate`, Vanguard directory | 16,838 present | 14,611 classes publish the tag across every N-1A archive; the remaining classes either filed no machine-readable prospectus or omitted the tag. N-CEN has no inception field, and EDGAR `dateOfOrganization` is the registrant trust's organization date, so it is deliberately not written as fund inception. |
| `category` | 38,044 | N-CEN classification flags; Nasdaq Fund Information API; issuer product pages | 1,095 (money-market classification and issuer-published categories) | N-CEN reports vehicle/strategy flags (ETF, index, money market, target date, fund of funds), not an investment style; they are exposed as the API `classification` object instead. Nasdaq's fund-info response returns `Category = N/A` for most classes. No official source publishes a Morningstar-style category. |
| `manager` | 6,059 | Form N-CEN `ADVISER` | 33,080 from eight quarters of N-CEN | Remaining registrants have not filed N-CEN in the scanned quarters or are trusts whose adviser row is blank. |
| `administrator` | 6,920 | Form N-CEN `ADMIN` | 32,219 from eight quarters of N-CEN | Same coverage limit as manager. |
| `net_assets` | 5,009 | N-PORT `FUND_REPORTED_INFO.NET_ASSETS`; N-CEN average net assets; N-CSR series net assets | 34,130 from N-PORT 2026q3, N-CEN and TSR filings | Funds whose series is absent from the latest N-PORT/N-CEN archives and whose TSR omits `AssetsNet` have no official figure for that period. |

## NAV and portfolio-holdings gaps

| Gap | Measured | Official source | Result |
| --- | ---: | --- | --- |
| No NAV | 13,464 | N-PORT/N-MFP/N-CEN snapshots; issuer NAV adapters; Nasdaq Fund Network | 25,675 funds have a NAV. 7,371 of the missing funds have no ticker. The ticker-bearing gaps were sampled against Nasdaq Fund Network: 0 of 60 random tickers returned a quote, so they are institutional/insurance classes not disseminated there. |
| No holdings | 5,767 | SEC N-PORT quarterly bulk, SEC N-MFP monthly bulk | 33,372 funds have holdings. The 4,492 missing series have **zero** overlap with the published bulk archives, so replaying earlier quarters recovers none of them. They are new series not yet in a published bulk quarter, or non-N-PORT filers. |

## Issuer-site automation results

Checked with a browser user agent:

- Reachable and parsed: Vanguard, SSGA/SPDR, Capital Group/American Funds,
  GraniteShares.
- Blocked or non-actionable: Fidelity, John Hancock (403), MassMutual (403),
  Invesco (406), Schwab (404), Direxion (403), Nationwide (JavaScript only),
  T. Rowe Price (JavaScript shell), American Century (500).
- ETF issuers such as Themes, Innovator, ProShares and Tidal expose no public
  structured endpoint.

## Commands

```bash
./.venv/bin/python scripts/audit_us_field_gaps.py
./.venv/bin/python scripts/audit_us_fund_gaps.py
./.venv/bin/python scripts/backfill_us_isins_from_sec_holdings.py --apply
./.venv/bin/python -m app.cli sync-sec-ncen-bulk --quarters 8
./.venv/bin/python -m app.cli sync-sec-nport-bulk
./.venv/bin/python -m app.cli sync-sec-nmfp-bulk --months 3 --all --assign-usd-nav
./.venv/bin/python -m app.cli sync-sec-rr-profiles --quarters 60
./.venv/bin/python -m app.cli sync-sec-ncsr-tsr --only-gaps --workers 8 --batch-size 100
./.venv/bin/python -m app.cli enrich-us-funds --tickers --net-assets --vanguard --issuer-navs --no-audit
./.venv/bin/python scripts/refresh_us_nasdaq_navs.py --missing-nav --delay 0.35
```

## Profile facts now imported from official filings

- **N-1A prospectus risk/return data sets** (`sync-sec-rr-profiles`) write
  `summary` (net/gross expense ratio, turnover, objective, strategy, class
  inception), `expense_ratio_history`, `performance` (1/3/5/10-year
  publisher-reported returns), `n1a_prospectus` and `inception_date` snapshots.
  Benchmark-index and load-adjusted rows are skipped. A full replay of every
  published archive wrote 319,346 snapshots for 67,401 classes with expenses,
  27,705 with returns, 26,912 with objective/strategy text and 14,611 with
  inception dates.
- **Tailored shareholder reports** (`sync-sec-ncsr-tsr`) add class-level
  `expense_ratio_history`, `performance`, `risk` (holdings count and turnover),
  `sector_allocation` and `ncsr_tsr_class` snapshots. The `--only-gaps` backfill
  parsed 3,444 filings for 1,182 registrants, matched 17,440 classes and filled
  1,562 tickers, 2,382 inception dates and 59 empty net-asset values.
- **Asset allocation** now comes from N-PORT: the filed `ASSET_CAT` of every
  position is summed per category into an `asset_allocation` snapshot (30,979
  fund/report-date rows).
- **`category` is not `classification`.** N-CEN vehicle/strategy flags are exposed
  as a separate API `classification` object with their own report date and source;
  they are never written to `funds.category`.
