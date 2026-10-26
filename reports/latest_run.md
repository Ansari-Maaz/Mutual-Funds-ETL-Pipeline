# Latest execution report

Generated at: 2026-10-26T11:22:42.169794+00:00

## Ingestion results

| Source | Status | Funds extracted | Funds loaded | NAV observations upserted | Rejected rows | Error |
|---|---|---:|---:|---:|---:|---|
| nl_euronext_fund_navs | Succeeded | 84 | 84 | 84 | 0 |  |

## Database counts

| Source | Funds | NAV observations |
|---|---:|---:|
| amf_geco | 28375 | 0 |
| asisa_cis_fund_list | 1945 | 0 |
| au_user_managed_funds | 96 | 4 |
| bmv_mexico_funds | 5151 | 3486 |
| cbi_authorised_ucits | 6725 | 0 |
| ch_six_fund_explorer_navs | 47 | 47 |
| cnmv_spanish_fund_register | 3116 | 0 |
| csrc_public_fund_index | 14170 | 0 |
| cvm_open_fund_data | 37875 | 252065 |
| de_bde_nonmonetary_funds | 6400 | 0 |
| de_bundesanzeiger_navs | 248 | 248 |
| dk_bde_nonmonetary_funds | 1486 | 0 |
| fca_authorised_funds | 3975 | 0 |
| fi_sweden_ucits_holdings | 726 | 0 |
| finma_swiss_fund_list | 2007 | 0 |
| fr_lacotebleue_navs | 90 | 90 |
| gsfm_unit_prices | 1 | 1 |
| hk_sfc_authorised_unit_trusts | 2255 | 0 |
| it_bde_nonmonetary_funds | 1326 | 0 |
| it_borsa_navs | 68 | 68 |
| lu_bde_nonmonetary_funds | 23955 | 0 |
| nl_bde_nonmonetary_funds | 1306 | 0 |
| nl_euronext_fund_navs | 84 | 84 |
| scotia_canada_daily_nav | 373 | 373 |
| sec_open_end_fund_classes | 39138 | 24846 |
| uk_ft_morningstar_prices | 253 | 253 |
| uk_fundslibrary_unit_prices | 33 | 33 |
| us_qqqm_etf | 1 | 1 |
| **Total** | **181225** | **281599** |
- Database used: Configured project PostgreSQL database.
- Raw snapshots are ignored by Git; source manifests record URLs, checksums, and sizes.
- Source rejects are recorded in source-specific JSONL files under `reports/`.
- Sample exports contain actual database rows: `sample_funds.json` and `sample_nav.json`.
- Commercial reuse rights require separate review for all providers.
