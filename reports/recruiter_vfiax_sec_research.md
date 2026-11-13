# Recruiter-referenced VFIAX research

The recruiter’s workflow was reproduced using SEC EDGAR records:

1. SEC mutual-fund ticker JSON maps `VFIAX` to CIK `36405`, series `S000002839`, and class `C000007774`.
2. SEC submissions JSON for CIK `0000036405` provides the filing history.
3. The matching N-PORT-P primary document was downloaded from accession `0000036405-26-000473` and checked for series `S000002839`.

## Extracted filing details

- Registered investment company: Vanguard Index Funds
- Series: VANGUARD 500 INDEX FUND
- Series ID: `S000002839`
- Reporting date: 2026-06-30
- Total assets: USD 1,673,632,288,919.41
- Net assets: USD 1,671,231,561,960.14
- Holdings extracted: 520

The holdings are available in:
`data/raw/united_states/vfiax_nport_holdings.csv`

The raw SEC files are retained in:

- `data/raw/united_states/sec_company_tickers_mf.json`
- `data/raw/united_states/vanguard_cik0000036405_filings.json`
- `data/raw/united_states/vfiax_nport_primary_doc.xml`

Daily NAV remains a separate price-history dataset. It is loaded from the
Nasdaq historical endpoint into `nav_observations`; N-PORT is quarterly holdings
and fund-detail reporting, not a daily NAV feed.
