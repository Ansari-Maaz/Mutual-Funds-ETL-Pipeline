// API-facing country identifiers are ISO 3166-1 alpha-3. Database/source
// connector identifiers remain alpha-2 for compatibility with source data.
const alpha3ByAlpha2 = {
  AE: 'UAE', AU: 'AUS', BR: 'BRA', CA: 'CAN', CH: 'CHE', CN: 'CHN',
  DE: 'DEU', DK: 'DNK', ES: 'ESP', FR: 'FRA', GB: 'GBR', HK: 'HKG',
  IE: 'IRL', IT: 'ITA', JP: 'JPN', KR: 'KOR', LU: 'LUX', MX: 'MEX',
  NL: 'NLD', RU: 'RUS', SE: 'SWE', SG: 'SGP', TW: 'TWN', US: 'USA', ZA: 'ZAF',
};
const alpha2ByAlpha3 = Object.fromEntries(Object.entries(alpha3ByAlpha2).map(([alpha2, alpha3]) => [alpha3, alpha2]));

function toAlpha3(code) {
  if (!code) return code;
  const normalized = String(code).toUpperCase();
  return alpha3ByAlpha2[normalized] || normalized;
}

function toAlpha2(code) {
  if (!code) return code;
  const normalized = String(code).toUpperCase();
  return alpha2ByAlpha3[normalized] || normalized;
}

module.exports = { alpha3ByAlpha2, toAlpha2, toAlpha3 };
