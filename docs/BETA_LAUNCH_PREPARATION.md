# FundFlow beta launch preparation

Prepared 2026-11-09. Migration is **not complete**: keep the current database and deployment as the source of truth until the restore gate below passes.

## Current state

- The preserved live source database is PostgreSQL 16.15 and contains 2,911,271,959 bytes: 187,100 funds, 358,282 NAV observations, 5,521,888 portfolio holdings, and 65 sources.
- A fresh custom-format dump, `FundFlow_supabase_restore_2026-11-09.dump`, was created directly from the preserved database: 249,558,119 bytes, SHA-256 `3ce355f5ee8de9b8bae08dc053979b794b403c174c4ec59d5c2c0ea039d3c3f9`. PostgreSQL 16.15 `pg_restore --list` reads it.
- The fresh dump was restored in a disposable PostgreSQL 17 container. All 10 public tables and exact row counts match. Columns, constraints, index facts, sequences, and extensions match. One partial-index definition has PostgreSQL 16/17 deparser text differences; its name, uniqueness, access method, key attributes, and validity match. See `reports/fundflow_restore_validation_2026-11-09.json`.
- The Supabase project `FundFlow-Database-Dump` (`zzkwcwzirdokefktxxsl`) is active in `ap-south-1`, on PostgreSQL 17. Direct SQL confirms an 11 MB empty database with zero public tables. The linked organization is on the Free plan; its 500 MB database quota and 2 GB fixed disk are below the 2.91 GB source. The project's `fundflow-db-dumps` Storage bucket is empty. The Pro plan currently includes 8 GB disk and costs $25/month; no plan change or paid restore has been authorized.
- The source was read-only checked directly. The existing local `.env` and deployed database target have not been changed. Do not infer a successful source-vs-Supabase comparison from the disposable local restore.
- Two prior Twelve Data sample runs are included in the generated report. They cover 10 US mutual-fund tickers on 2026-10-30 and 2026-11-05; they are not a fresh complete-fund-universe run.
- Nasdaq official historical data have been fetched for the same 10 mutual funds plus QQQM, covering 2026-10-30 through 2026-11-06 (66 observations). The local FundFlow database was refreshed with these values after writing a rollback backup at `reports/nasdaq_official_refresh_backup_2026-11-09.json`.
- `reports/fundflow_beta_validation.html` includes the official-source reconciliation. All 25 saved Twelve Data prices match Nasdaq at cent precision (17 equal as raw decimals, 8 differ only below one cent); 41 official observations lack a saved Twelve Data value and remain unverified. All 21 fund/date records have no mismatches among comparable fields, while the overall result remains partial because restricted/unavailable and unvalidated fields are not counted as matches. QQQM observations are ETF market prices, not NAVs. This is not a full-universe or holdings validation.

## Comparison report

Generate a consolidated HTML, JSON, and field-level CSV report:

```bash
python scripts/build_beta_comparison_report.py
```

Refresh the official comparison window (dry-run by default; `--apply` backs up and upserts into the configured local FundFlow database):

```bash
python scripts/sync_nasdaq_official_comparison_data.py
python scripts/sync_nasdaq_official_comparison_data.py --apply
```

Attach database parity details from a local or cloud restore check:

```bash
python scripts/build_beta_comparison_report.py \
  --database-validation-json reports/supabase_restore_validation.json
```

Pass run JSON files explicitly with repeated `--input path.json`. Use `--output-dir` and `--stem` to preserve each run as a separate report. The report scopes missing results only to records actually requested, separates `unavailable_to_subscription` from `mismatch`, and carries source run dates and limitations forward.

For a fresh curated sample (10–20 US mutual-fund symbols; two standard calls per symbol):

```bash
TWELVE_DATA_API_KEY='(set in secret manager or shell environment)' \
  python scripts/compare_twelvedata_us_sample.py --date YYYY-MM-DD
```

The sample script also accepts `--tickers` and writes a dated JSON and Markdown response summary. It uses the existing local FundFlow database read-only and prompts with hidden input if no key is configured. Never put the API key in chat, a checked-in file, command output, or a report. Premium full-directory and holdings/composition endpoints are not called by default; review Twelve Data entitlements and credit cost before enabling them.

For reusable mutual-fund or ETF checks, including an optional historical window:

```bash
python scripts/compare_twelvedata_universe.py \
  --kind etf --tickers QQQM --date 2026-11-06 --history-limit 5 --max-credits 2
```

This framework exact-matches symbols, compares directory metadata and NAV/history records, and keeps missing, unavailable, and mismatched fields separate. Holdings/composition checks require `--include-holdings` and a cap of at least 200 credits per symbol via `--max-credits`; the default does not spend those premium credits. If the API does not provide an as-of date for holdings, the framework retains both lists but does not claim their weights match.

Compare the source database with a restored PostgreSQL URL, or an isolated container, and save row/schema parity:

```bash
export SUPABASE_DATABASE_URL='(set through your deployment secret manager)'
python scripts/validate_database_restore.py --target-env SUPABASE_DATABASE_URL
```

Use `--target-docker-container NAME` for an isolated local restore target. `DATABASE_URL` is read from the configured local environment as the source by default.

## Matching and reporting rules

- The current live sample matches by exact requested ticker and exact returned symbol; ambiguous local ticker rows cause a lookup error rather than arbitrary selection.
- Values are compared only when both observations exist. `unavailable_to_subscription` means the provider returned an add-on access sentinel; it is not a mismatch. The consolidated report classifies exchange metadata not stored in FundFlow as `not_collected_in_fundflow`, and OHLC fields as `not_comparable` because FundFlow stores a single daily NAV.
- NAV/close equality is recorded exactly and to the nearest cent, but is labeled vendor-to-vendor parity because the local US values may be Yahoo Finance prices rather than issuer NAV.
- FundFlow's single daily NAV is never reused as OHLC. Missing values and unsupported fields are distinct.
- Current sample runs do not validate ISIN/CUSIP (provider access sentinel), historical NAV, ETF coverage, holdings, or full universe membership. Do not report these as verified.

## Supabase restore gate and rollback

1. Ensure the target has sufficient database capacity (source is about 2.9 GB before restore overhead), confirm backup/retention settings, and retain the current database and deployment URL.
2. Reassemble the private dump parts according to the uploaded manifest; verify each part and the final SHA-256 before restore. Never put the connection password in a script, log, or repository.
3. Restore into the empty Supabase project using a PostgreSQL 16 `pg_restore` client. Review extension/ownership/role statements and Supabase compatibility before the actual restore; preserve data and schema objects and document any provider-managed differences. Do not restore over a non-empty target without a reviewed rollback plan.
4. Compare source and target table lists, row counts, min/max dates, sequences, index/constraint/foreign-key definitions, and extensions with `scripts/validate_database_restore.py`. Validate representative historical records and application queries. Preserve machine-readable comparison output.
5. Only after those checks pass, change the deployment secret `DATABASE_URL` to the Supabase URL with `sslmode=require` and use the connection mode appropriate for the deployment network. Restart and run smoke checks; retain the old URL and a fresh backup for immediate rollback.

Python uses SQLAlchemy/psycopg and accepts `sslmode=require`; Node `pg` receives the same URL. The `.env.example` files show placeholder URL shapes only. Configure real credentials only in the deployment secret store. The active `.env` is intentionally untouched.

## Remaining beta launch blockers

- Upgrade/capacity approval for the Supabase target, then complete and verify the restore.
- Restore and verify the Supabase target, then produce actual source-to-Supabase parity results.
- Fresh API validation over an agreed fund and ETF sample, including history; actual Twelve Data key must be configured locally in a secret store.
- Holdings, full universe, and restricted metadata must be explicitly scoped against the selected Twelve Data plan before spending premium credits.
- Complete staging smoke tests and deployment rollback rehearsal after the restore passes.
