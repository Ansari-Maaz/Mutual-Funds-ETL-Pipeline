const fs = require('node:fs');
const path = require('node:path');
const { projectRoot } = require('../config');

const raw = JSON.parse(fs.readFileSync(path.join(projectRoot, 'reports/source_catalogue.json'), 'utf8'));
const entries = new Map(raw.map((row) => [row.source_id, row]));
// Spain is an additional demonstration dataset, outside the 20 required and
// four expansion markets in the assignment.
const assignmentCountryCodes = new Set([
  'US', 'CA', 'MX', 'GB', 'DE', 'FR', 'IT', 'CH', 'NL', 'DK', 'SE',
  'JP', 'CN', 'KR', 'AU', 'SG', 'HK', 'TW', 'RU', 'BR', 'LU', 'IE',
  'AE', 'ZA',
]);
const countries = new Map();
for (const row of raw) {
  if (!countries.has(row.country_code)) countries.set(row.country_code, {
    code: row.country_code,
    name: row.country_name,
    region: row.region,
    assignmentScope: assignmentCountryCodes.has(row.country_code),
  });
}
const runnableSources = new Set([
  'cvm_open_fund_data', 'csrc_public_fund_index', 'gsfm_unit_prices', 'asisa_cis_fund_list',
  'finma_swiss_fund_list', 'fca_authorised_funds', 'sec_open_end_fund_classes',
  'cnmv_spanish_fund_register', 'fi_sweden_ucits_holdings', 'cbi_authorised_ucits', 'amf_geco', 'us_qqqm_etf', 'scotia_canada_daily_nav', 'bmv_mexico_funds', 'uk_fundslibrary_unit_prices', 'uk_ft_morningstar_prices',
  'dk_bde_nonmonetary_funds', 'de_bundesanzeiger_navs', 'it_borsa_navs', 'ch_six_fund_explorer_navs', 'fr_lacotebleue_navs',
  'de_bde_nonmonetary_funds', 'it_bde_nonmonetary_funds',
  'nl_bde_nonmonetary_funds', 'lu_bde_nonmonetary_funds',
  'hk_sfc_authorised_unit_trusts',
  'au_user_managed_funds',
]);

module.exports = { entries, countries, runnableSources, assignmentCountryCodes };
