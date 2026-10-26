# Latest execution report

Generated at: 2026-10-26T06:53:57.629271+00:00

## Ingestion results

| Source | Status | Funds extracted | Funds loaded | NAV observations upserted | Rejected rows | Error |
|---|---|---:|---:|---:|---:|---|
| cvm_open_fund_data | Succeeded | 37875 | 37875 | 252065 | 697 |  |
| csrc_public_fund_index | Succeeded | 14170 | 14170 | 0 | 0 |  |
| gsfm_unit_prices | Succeeded | 1 | 1 | 1 | 22 |  |
| asisa_cis_fund_list | Succeeded | 1945 | 1945 | 0 | 0 |  |
| finma_swiss_fund_list | Succeeded | 2007 | 2007 | 0 | 0 |  |
| fca_authorised_funds | Succeeded | 3975 | 3975 | 0 | 0 |  |
| sec_open_end_fund_classes | Failed | 9300 | 9121 | 6446 | 0 | ValidationError: 1 validation error for CanonicalNav
nav
  Input should be greater than 0 [type=greater_than, input_value='0', input_type=str]
    For further information visit https://errors.pydantic.dev/2.14/v/greater_than |
| cnmv_spanish_fund_register | Succeeded | 3116 | 3116 | 0 | 0 |  |
| fi_sweden_ucits_holdings | Succeeded | 726 | 726 | 0 | 0 |  |
| cbi_authorised_ucits | Succeeded | 6725 | 6725 | 0 | 0 |  |
| amf_geco | Succeeded | 28375 | 28375 | 0 | 0 |  |
| dk_bde_nonmonetary_funds | Succeeded | 1486 | 1486 | 0 | 101 |  |
| de_bde_nonmonetary_funds | Succeeded | 6400 | 6400 | 0 | 0 |  |
| it_bde_nonmonetary_funds | Succeeded | 1326 | 1326 | 0 | 0 |  |
| nl_bde_nonmonetary_funds | Succeeded | 1306 | 1306 | 0 | 0 |  |
| lu_bde_nonmonetary_funds | Succeeded | 23955 | 23955 | 0 | 0 |  |
| hk_sfc_authorised_unit_trusts | Succeeded | 2255 | 2255 | 0 | 154 |  |
| au_user_managed_funds | Succeeded | 96 | 96 | 4 | 0 |  |
| us_qqqm_etf | Succeeded | 1 | 1 | 1 | 0 |  |
| scotia_canada_daily_nav | Succeeded | 373 | 373 | 373 | 0 |  |
| bmv_mexico_funds | Succeeded | 5151 | 5151 | 3479 | 0 |  |
| uk_fundslibrary_unit_prices | Succeeded | 33 | 33 | 33 | 0 |  |
| uk_ft_morningstar_prices | Succeeded | 253 | 253 | 253 | 0 |  |
| de_bundesanzeiger_navs | Succeeded | 248 | 248 | 248 | 0 |  |

## Database counts

| Source | Funds | NAV observations |
|---|---:|---:|
| amf_geco | 28375 | 0 |
| asisa_cis_fund_list | 1945 | 0 |
| au_user_managed_funds | 96 | 4 |
| bmv_mexico_funds | 5151 | 3486 |
| cbi_authorised_ucits | 6725 | 0 |
| cnmv_spanish_fund_register | 3116 | 0 |
| csrc_public_fund_index | 14170 | 0 |
| cvm_open_fund_data | 37875 | 252065 |
| de_bde_nonmonetary_funds | 6400 | 0 |
| de_bundesanzeiger_navs | 248 | 248 |
| dk_bde_nonmonetary_funds | 1486 | 0 |
| fca_authorised_funds | 3975 | 0 |
| fi_sweden_ucits_holdings | 726 | 0 |
| finma_swiss_fund_list | 2007 | 0 |
| gsfm_unit_prices | 1 | 1 |
| hk_sfc_authorised_unit_trusts | 2255 | 0 |
| it_bde_nonmonetary_funds | 1326 | 0 |
| lu_bde_nonmonetary_funds | 23955 | 0 |
| nl_bde_nonmonetary_funds | 1306 | 0 |
| scotia_canada_daily_nav | 373 | 373 |
| sec_open_end_fund_classes | 39138 | 24846 |
| uk_ft_morningstar_prices | 253 | 253 |
| uk_fundslibrary_unit_prices | 33 | 33 |
| us_qqqm_etf | 1 | 1 |
| **Total** | **180936** | **281310** |
- Database used: Configured project PostgreSQL database.
- Raw snapshots are ignored by Git; source manifests record URLs, checksums, and sizes.
- Source rejects are recorded in source-specific JSONL files under `reports/`.
- Sample exports contain actual database rows: `sample_funds.json` and `sample_nav.json`.
- Commercial reuse rights require separate review for all providers.
