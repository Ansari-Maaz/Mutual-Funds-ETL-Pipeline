# SEC mutual-fund ticker JSON

The SEC endpoint is now present at:
`data/raw/united_states/sec_company_tickers_mf.json`

- URL: https://www.sec.gov/files/company_tickers_mf.json
- Records downloaded: 28,610
- Fields: CIK, series ID, class ID, ticker symbol
- SHA-256: `9e376ab376494057f172ad231929b9709650e95db885cf8c8e1c79b35e18864c`

This file does not contain company or fund names and does not contain NAVs. It
is imported as a supplemental ticker mapping into the existing SEC fund-master
connector by matching the SEC class ID. The CSV fund master remains the source
of names and class metadata, avoiding duplicate fund rows.
