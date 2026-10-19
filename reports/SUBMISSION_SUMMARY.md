# Submission summary

## Imported datasets

- 17 connectors run against PostgreSQL: 11 existing sources plus official open-ended fund lists for Germany, Italy, Netherlands, Denmark and Luxembourg, and the Hong Kong SFC public-offer list. Spain remains an additional market outside the requested scope.
- The BDE country lists provide a European code, LEI when available, fund name, manager, policy and open/closed status. Only open-ended records were loaded. These lists include UCITS and AIF categories and have no NAV/currency.
- The Hong Kong SFC product list provides fund/sub-fund names and SFC CE numbers for public-offer products. It includes overseas domiciles, so `domicile_country` is deliberately null.
- Every downloaded dataset has a source manifest with URL, byte count and SHA-256; raw snapshots are retained locally under `data/raw/`.

## Current database snapshot

- **Funds:** 162,584
- **NAV observations:** 252,030
- **New imports:** Germany 6,400; Italy 1,326; Netherlands 1,306; Denmark 1,486; Luxembourg 23,955; Hong Kong public-offer products 2,255.
- **Remaining core markets:** Canada, Mexico, Japan, South Korea, Singapore, Taiwan and Russia. The UAE remains as an expansion-market gap.
- Brazil CVM supplies 252,029 NAV observations; Australia contributes one explicitly AUD-denominated observation. The new country lists are fund-master snapshots without NAV.

## Reports

`reports/latest_run.md`, `reports/sample_funds.json`, `reports/sample_nav.json`, `reports/source_catalogue.json` and `reports/global_mutual_fund_source_inventory.xlsx` reflect the current database and connector catalog.

```sh
python -m app.cli sync-sources
python -m app.cli run --all
python -m app.cli inventory
```

Provider licensing and commercial reuse rights still require review.
