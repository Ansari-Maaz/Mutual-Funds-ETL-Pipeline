# Latest execution report

Generated at: 2026-10-19T19:28:22.558665+00:00

## Ingestion results

| Source | Status | Funds extracted | Funds loaded | NAV observations upserted | Rejected rows | Error |
|---|---|---:|---:|---:|---:|---|
| cvm_open_fund_data | Succeeded | 25678 | 25678 | 252029 | 697 |  |

## Database counts

| Source | Funds | NAV observations |
|---|---:|---:|
| amf_geco | 28375 | 0 |
| asisa_cis_fund_list | 1945 | 0 |
| cbi_authorised_ucits | 6725 | 0 |
| cnmv_spanish_fund_register | 3116 | 0 |
| csrc_public_fund_index | 14170 | 0 |
| cvm_open_fund_data | 25678 | 252029 |
| de_bde_nonmonetary_funds | 6400 | 0 |
| dk_bde_nonmonetary_funds | 1486 | 0 |
| fca_authorised_funds | 3975 | 0 |
| fi_sweden_ucits_holdings | 726 | 0 |
| finma_swiss_fund_list | 2007 | 0 |
| gsfm_unit_prices | 1 | 1 |
| hk_sfc_authorised_unit_trusts | 2255 | 0 |
| it_bde_nonmonetary_funds | 1326 | 0 |
| lu_bde_nonmonetary_funds | 23955 | 0 |
| nl_bde_nonmonetary_funds | 1306 | 0 |
| sec_open_end_fund_classes | 39138 | 0 |
| **Total** | **162584** | **252030** |
- Database used: Configured project PostgreSQL database.
- Raw snapshots are ignored by Git; source manifests record URLs, checksums, and sizes.
- Source rejects are recorded in source-specific JSONL files under `reports/`.
- Sample exports contain actual database rows: `sample_funds.json` and `sample_nav.json`.
- Commercial reuse rights require separate review for all providers.
