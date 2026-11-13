# Submission summary

## Imported datasets

- Official country sources include open-ended fund lists for Germany, Italy, Netherlands, Denmark and Luxembourg; the Hong Kong SFC public-offer list; Japan IMAJ and FSA NISA fund lists and IMAJ monthly new-fund records; and South Korea's IBK public fund-information file. Connector counts change as source snapshots are refreshed. Spain remains an additional market outside the requested scope.
- The BDE country lists provide a European code, LEI when available, fund name, manager, policy and open/closed status. Only open-ended records were loaded. These lists include UCITS and AIF categories and have no NAV/currency.
- The Hong Kong SFC product list provides fund/sub-fund names and SFC CE numbers for public-offer products. It includes overseas domiciles, so `domicile_country` is deliberately null.
- Every downloaded dataset has a source manifest with URL, byte count and SHA-256; raw snapshots are retained locally under `data/raw/`.

## Current database snapshot

- **Fund records:** 187,100
- **NAV observations:** 308,812
- **Portfolio holdings:** 5,436,178
- **Database recovery (2026-11-06):** The app had been connected to a newly created PostgreSQL volume instead of the preserved project volume. The original volume had 183,227 fund records and 5,436,178 holdings. Japan and South Korea then added 3,873 source records, bringing the live total to 187,100. See `reports/database_recovery_2026-11-06.md`.
- **Japan and South Korea import (2026-11-06):** 3,873 source records loaded across four sources (2,364 IMAJ growth-quota; 366 FSA tsumitate; 11 IMAJ monthly new-fund; 1,132 IBK products). The Japanese lists overlap. These imports added 3,862 profile snapshots and no NAV rows.
- **New imports:** Germany 6,400; Italy 1,326; Netherlands 1,306; Denmark 1,486; Luxembourg 23,955; Hong Kong public-offer products 2,255.
- **Remaining core markets without an imported dataset:** Canada, Mexico, Singapore, Taiwan and Russia. Japan has NISA-eligible domestic fund subsets, not a complete market master. The South Korea import covers IBK-handled products only and leaves domicile null; it is not a complete domestic-fund universe. The UAE remains as an expansion-market gap.
- Brazil CVM and other connected sources provide NAV history; Japan and South Korea imports are fund/profile snapshots without NAV.

## Reports

`reports/latest_run.md`, `reports/sample_funds.json`, `reports/sample_nav.json`, `reports/source_catalogue.json` and `reports/global_mutual_fund_source_inventory.xlsx` reflect the current database and connector catalog.

```sh
python -m app.cli sync-sources
python -m app.cli run --all
python -m app.cli inventory
```

Provider licensing and commercial reuse rights still require review.
