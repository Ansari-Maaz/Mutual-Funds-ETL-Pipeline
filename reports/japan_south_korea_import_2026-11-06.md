# Japan and South Korea fund imports — 2026-11-06

Imported into the configured local PostgreSQL database using the registered source connectors. These are fund/profile records only; none of the files below provides NAV history.

| Source | Snapshot date | Extracted / loaded | Profile snapshots | NAV rows | Scope |
|---|---|---:|---:|---:|---|
| `jp_imaj_nisa_growth_funds` | Current IMAJ workbook | 2,364 / 2,364 | 2,364 | 0 | Domestic non-listed funds eligible for Japan's NISA growth quota |
| `jp_fsa_tsumitate_funds` | 2026-10-23 | 366 / 366 | 366 | 0 | NISA tsumitate-eligible non-ETF investment trusts |
| `jp_imaj_new_funds` | Current IMAJ monthly workbook | 11 / 11 | 0 | 0 | Newly announced funds in the published sheet types |
| `kr_ibk_fund_information` | 2025-12-31 | 1,132 / 1,132 | 1,132 | 0 | Products handled by IBK; includes period returns, risk grade, and fees |

The Japan lists overlap, so source counts must not be added to claim a count of unique Japanese funds. IMAJ supplies a native association code for its growth list; the FSA and monthly new-fund imports use generated stable source IDs because those sheets do not publish a native code. The Korean file does not report domicile, currency, or NAV, so domicile and currency are left null.

The Korean records are attributed to the South Korea **source market** for browsing, while their actual domicile remains unknown. Fund search therefore includes records whose domicile is unknown when their registered source is Korean. The IBK CSV reports period returns and fees, not dated NAV observations or portfolio positions; those values are not synthesized from returns. No official, openly accessible bulk NAV-and-holdings feed was verified for import. KOFIA's electronic disclosure portal supports individual base-price lookup, while its OpenAPI requires application and approval.

Raw files are stored under `data/raw/japan/` and `data/raw/south_korea/` (Git-ignored). SHA-256 and source details are recorded in `reports/jp_imaj_nisa_growth_dataset_manifest.json`, `reports/jp_fsa_tsumitate_dataset_manifest.json`, `reports/jp_imaj_new_funds_dataset_manifest.json`, and `reports/kr_ibk_fund_information_dataset_manifest.json`.

## Official sources

- [IMAJ NISA growth-quota fund list](https://www.imaj.or.jp/find/nisa_growth_productslist/)
- [Japan FSA NISA tsumitate-quota fund list](https://www.fsa.go.jp/policy/nisa2/products/index.html)
- [IMAJ monthly new-fund sheets](https://www.imaj.or.jp/find/newfunds/index.html)
- [South Korea data.go.kr IBK fund-information dataset](https://www.data.go.kr/data/15020770/fileData.do)
- [KOFIA fund information portal](https://fund.kofia.or.kr/fs/fund/html/fundMain.html) and [electronic disclosure service](https://dis.kofia.or.kr/) were reviewed; a complete public bulk feed was not verified.

This is a partial source-based expansion, not a complete Japan or South Korea market register. IMAJ's broader searchable fund library prohibits automated scraping, so it was not scraped. Check provider terms before redistribution or commercial use.
