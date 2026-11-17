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
| `ticker` | 9,596 | SEC `company_tickers_mf.json` (class ID → symbol) and the SEC series/class master | 29,543 present; 4 additional classes recovered from the live feed | Classes absent from both files publish no symbol: variable-insurance separate accounts, 529 plan classes, and institutional classes. Borrowing a sibling class's ticker would be false. |
| `isin` | 38,970 | SEC N-PORT `IDENTIFIERS` (portfolio security CUSIP/ISIN), with check-digit validation and exact ticker/name agreement | 169 classes backed by a validated CUSIP/ISIN pair | The SEC series/class master explicitly has no ISIN. N-PORT identifiers describe portfolio securities, not the filer's own share classes. There is no official bulk US fund-ISIN feed, so a class that is never held by another filer cannot be assigned one. |
| `inception_date` | 38,747 | Form N-CEN; SEC EDGAR submissions `dateOfOrganization`; N-1A prospectus XBRL | 392 from Vanguard's official directory | N-CEN has no inception field. EDGAR full-text has no `FundInceptionDate` XBRL tag, and `dateOfOrganization` is the registrant trust's organization date — often decades before an individual series launched — so it is deliberately not written as fund inception. |
| `category` | 38,044 | N-CEN classification flags; Nasdaq Fund Information API; issuer product pages | 1,095 (money-market classification and issuer-published categories) | N-CEN reports vehicle/strategy flags (ETF, index, money market, target date, fund of funds), not an investment style. Nasdaq's fund-info response returns `Category = N/A` for most classes. No official source publishes a Morningstar-style category. |
| `manager` | 6,059 | Form N-CEN `ADVISER` | 33,080 from eight quarters of N-CEN | Remaining registrants have not filed N-CEN in the scanned quarters or are trusts whose adviser row is blank. |
| `administrator` | 6,920 | Form N-CEN `ADMIN` | 32,219 from eight quarters of N-CEN | Same coverage limit as manager. |
| `net_assets` | 5,068 | N-PORT `FUND_REPORTED_INFO.NET_ASSETS`; N-CEN average net assets | 34,071 from the newest N-PORT quarter (2026q3) plus N-CEN | Funds whose series is absent from the latest N-PORT/N-CEN archives have no official figure for that period. |

## NAV and portfolio-holdings gaps

| Gap | Measured | Official source | Result |
| --- | ---: | --- | --- |
| No NAV | 13,464 | N-PORT/N-MFP/N-CEN snapshots; issuer NAV adapters; Nasdaq Fund Network | 25,675 funds have a NAV. 9,414 of the missing funds have no ticker. The 4,050 ticker-bearing gaps were sampled against Nasdaq Fund Network: 0 of 60 random tickers returned a quote, so they are institutional/insurance classes not disseminated there. |
| No holdings | 5,767 | SEC N-PORT quarterly bulk, SEC N-MFP monthly bulk | 33,372 funds have holdings. The 4,492 missing series have **zero** overlap with the 2026q2, 2026q1 and 2025q4 bulk archives, so replaying earlier quarters recovers none of them. They are new series not yet in a published bulk quarter, or non-N-PORT filers. |

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
./.venv/bin/python -m app.cli enrich-us-funds --tickers --net-assets --vanguard --issuer-navs --no-audit
./.venv/bin/python scripts/refresh_us_nasdaq_navs.py --missing-nav --delay 0.35
```
