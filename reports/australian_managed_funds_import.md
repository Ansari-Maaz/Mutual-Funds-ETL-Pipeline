# Australian managed-fund CSV import

## Imported source

- File: `data/raw/australia/australian_managed_funds.csv`
- Origin: user-provided file
- SHA-256: `c2737e86c45a78772893b5babf33c3ecf31c5d933fdd4bd29a5f84222201f97c`
- ETL source ID: `au_user_managed_funds`

## Result

| Metric | Value |
|---|---:|
| Rows supplied | 96 |
| Rows imported | 96 |
| Rejected rows | 0 |
| Managers | 32 |
| Distinct subcategories | 71 |
| Currency | AUD for all 96 rows |
| ISIN values supplied | 0 |
| NAV values supplied in the original catalogue | 0 |
| NAV observations imported after official-source research | 4 |

## Imported fields

`fund_name`, `manager`, `subcategory`, `structure`, `base_currency`, and `official_source` are loaded into the normalized fund table as fund name, manager/provider, category, fund type, currency, and official URL.

The `isin` and `nav_aud` columns are present in the file but blank for every record. The ETL deliberately keeps ISIN and NAV null. It does not generate identifiers or values from fund names.

## NAV research result

The provider URLs in the CSV identify fund-manager websites. They are not a shared, complete Australian daily-NAV feed, and the supplied file contains no valuation date. I researched the official Vanguard Australia price table and imported four exact fund-name matches with an explicitly labelled AUD NAV and valuation date (2026-10-09): Conservative Index, Balanced Index, Growth Index, and High Growth Index. The source page states that managed-fund unit prices are updated daily and shows the NAV, buy price, sell price, currency, and date.

The four researched records are stored in `data/raw/australia/australian_managed_fund_navs.csv` with the source URL and are loaded by the same ETL source ID. The existing GSFM unit-price connector remains a separate official source and has one validated AUD NAV observation. Colonial First State currently publishes entry/exit prices rather than a field explicitly labelled NAV, and Australian Ethical's dynamic unit-price page needs stable fund-class matching before its values can be safely assigned to this catalogue; those values were not relabelled as NAV.

Research sources:

- Vanguard Australia managed funds and ETF prices: https://www.vanguard.com.au/adviser/invest/funds-and-etfs?tab=prices
- Colonial First State unit prices and performance: https://www.colonialfirststate.com.au/Price_performance/performanceNPrice.aspx
- Australian Ethical managed-fund performance and unit prices: https://www.australianethical.com.au/investments/managed-funds/performance-and-prices/
