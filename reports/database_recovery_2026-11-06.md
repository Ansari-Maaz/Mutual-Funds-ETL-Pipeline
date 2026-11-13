# Database recovery — 2026-11-06

## Current live database

| Metric | Preserved original database | Japan and South Korea added | Current total |
|---|---:|---:|---:|
| Fund records | 183,227 | 3,873 | 187,100 |
| NAV observations | 308,812 | 0 | 308,812 |
| Portfolio holdings | 5,436,178 | 0 | 5,436,178 |

The dashboard API at `/api/v1/stats` reports the same current fund and NAV totals. The four new sources are present in the same live database: 2,364 IMAJ growth-quota rows, 366 FSA tsumitate rows, 11 IMAJ monthly new-fund rows, and 1,132 IBK South Korean records.

## Cause and correction

The project was running against a newly created Docker volume, `mfetlpipeline_pgdata`, instead of its preserved original volume, `mf-etl-pipeline-pgdata`. The newly created database did not include the original 183,227 fund records or 5,436,178 holdings. The original volume still contained those records and the previous ETL history.

The project Compose configuration now explicitly uses the preserved `mf-etl-pipeline-pgdata` volume. The older database was already at the app's current Alembic head (`0011_currency_basis`). Japan and South Korea sources were synchronized and imported into that database. The newer, separate database volume was left intact as a fallback.

## Verification

- Original volume before the new imports: 183,227 funds, 308,812 NAV observations, and 5,436,178 holdings.
- Current database after the imports: 187,100 funds, 308,812 NAV observations, and 5,436,178 holdings.
- The API reports `fundRecords: 187100` and `navObservations: 308812`.
- `FundFlow_database_dump.dump` is the refreshed PostgreSQL custom-format dump of this current database; `pg_restore --list` can read it.

Fund counts are source-scoped records. They are not a deduplicated count of unique products across feeds or a claim of complete global market coverage.
