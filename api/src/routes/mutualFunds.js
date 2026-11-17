const express = require('express');
const router = express.Router();
const { toAlpha2 } = require('../services/countryCodes');

// This compatibility surface uses FundFlow's own stored data. It never
// requests or copies Twelve Data values. Snapshot payloads retain provenance.
const profileSections = new Set([
  'summary', 'performance', 'risk', 'ratings', 'composition',
  'purchase_info', 'sustainability',
]);
const datasetForSection = { summary: 'summary', performance: 'performance', risk: 'risk',
  ratings: 'ratings', composition: 'composition', purchase_info: 'purchase_info',
  sustainability: 'sustainability' };
const safeJson = (value) => value && typeof value === 'object' ? value : {};
const dateOnly = (value) => value == null ? null : value instanceof Date
  ? `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  : String(value).slice(0, 10);
const pick = (value, ...keys) => {
  for (const key of keys) if (value?.[key] !== undefined && value[key] !== null && value[key] !== '') return value[key];
  return null;
};
const countryName = (code) => ({ US: 'United States', CA: 'Canada', GB: 'United Kingdom',
  DE: 'Germany', FR: 'France', JP: 'Japan', KR: 'South Korea', AU: 'Australia',
  BR: 'Brazil', CH: 'Switzerland', CN: 'China', HK: 'Hong Kong', SG: 'Singapore',
  IT: 'Italy', NL: 'Netherlands', DK: 'Denmark', SE: 'Sweden', LU: 'Luxembourg',
  IE: 'Ireland', MX: 'Mexico', ZA: 'South Africa', AE: 'United Arab Emirates',
  TW: 'Taiwan', RU: 'Russia' })[code] || code;

async function profileRows(pool, fundIds) {
  if (!fundIds.length) return new Map();
  const { rows } = await pool.query(`
    SELECT fund_id,dataset,payload,source_id,source_url,source_report_date,retrieved_at
    FROM fund_profile_snapshots WHERE fund_id=ANY($1::int[])
    ORDER BY fund_id,dataset,source_report_date ASC NULLS FIRST,retrieved_at,id
  `, [fundIds]);
  const result = new Map();
  for (const row of rows) {
    if (!result.has(row.fund_id)) result.set(row.fund_id, new Map());
    if (!result.get(row.fund_id).has(row.dataset)) result.get(row.fund_id).set(row.dataset, []);
    result.get(row.fund_id).get(row.dataset).push(row);
  }
  return result;
}

const latestSnapshot = (snapshots, dataset) => snapshots.get(dataset)?.at(-1) || null;
const snapshotPayload = (snapshots, dataset) => safeJson(latestSnapshot(snapshots, dataset)?.payload);
const numeric = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
};
const snapshotMeta = (row) => row ? ({ source_id: row.source_id, source_url: row.source_url,
  report_date: dateOnly(row.source_report_date), retrieved_at: row.retrieved_at }) : null;
const pctFraction = (value, payload) => {
  const parsed = numeric(value);
  return parsed === null ? null : (payload.unit === 'percent' ? parsed / 100 : parsed);
};

function buildSummary(fund, snapshots, latestNav) {
  const summary = snapshotPayload(snapshots, 'summary');
  const summaryRows = snapshots.get('summary') || [];
  const sourceSummaryValue = (...keys) => {
    for (const row of [...summaryRows].reverse()) {
      for (const key of keys) {
        const value = row.payload?.[key];
        if (value !== undefined && value !== null && value !== '') return value;
      }
    }
    return null;
  };
  const perfRows = snapshots.get('performance') || [];
  const ytdRow = [...perfRows].reverse().find((row) => ['ytdReturn', 'CYTD', 'ytd_return'].includes(row.payload?.metric) || row.payload?.values?.CYTD !== undefined);
  const ytdValue = ytdRow?.payload?.metric ? ytdRow.payload.value : ytdRow?.payload?.values?.CYTD;
  const ytdValueIsPercent = ytdRow?.payload?.metric ? ytdRow.payload.unit === 'percent' : ytdValue !== undefined;
  const expense = [...(snapshots.get('expense_ratio_history') || [])].reverse().find((row) => numeric(row.payload?.reported_value) !== null);
  const aum = [...(snapshots.get('aum_history') || [])].reverse().find((row) => numeric(row.payload?.net_assets ?? row.payload?.amount ?? row.payload?.reported_value) !== null);
  const yieldRow = latestSnapshot(snapshots, 'yields');
  const yieldPayload = safeJson(yieldRow?.payload);
  const classificationRow = latestSnapshot(snapshots, 'classification');
  const classification = safeJson(classificationRow?.payload);
  const classificationFlags = Object.fromEntries(Object.entries(classification)
    .filter(([key]) => !['effective_date', 'accession_number', 'source_url'].includes(key)));
  const manager = fund.manager || summary.manager || null;
  const result = {
    symbol: fund.ticker || summary.ticker || summary.class_ticker || null,
    name: fund.name,
    fund_family: fund.provider || summary.provider || summary.fund_family || null,
    fund_type: fund.fund_type || summary.fund_type || null,
    category: fund.category || summary.category || null,
    category_basis: fund.category ? 'publisher-reported classification (issuer directory or SEC N-CEN money-market flag); not a Morningstar/Lipper style category' : null,
    currency: fund.currency || summary.currency || latestNav?.currency || null,
    share_class_inception_date: dateOnly(fund.inception_date) || sourceSummaryValue('share_class_inception_date','inception_date') || null,
    ytd_return: ytdValue === undefined ? null : pctFraction(ytdValue, ytdValueIsPercent ? { ...ytdRow.payload, unit: 'percent' } : ytdRow.payload),
    // Only label a reported rate as net when the source names the basis.
    expense_ratio_net: numeric(summary.expense_ratio_net) ?? (/\bnet\b/i.test(expense?.payload?.measure || '') ? numeric(expense.payload.reported_value) / (expense.payload.unit === 'percent' ? 100 : 1) : null),
    yield: numeric(summary.yield),
    nav: numeric(latestNav?.nav),
    min_investment: null,
    turnover_rate: numeric(sourceSummaryValue('turnover_rate')),
    net_assets: numeric(fund.net_assets ?? aum?.payload?.net_assets ?? aum?.payload?.amount ?? aum?.payload?.reported_value),
    overview: sourceSummaryValue('objective','investment_objective','overview'),
    people: manager ? [{ name: manager, tenure_since: sourceSummaryValue('manager_tenure_since') }] : [],
    classification: Object.keys(classificationFlags).length ? {
      ...classificationFlags,
      basis: 'SEC Form N-CEN reported classification flags: vehicle and strategy attributes, not an investment-style category.',
      report_date: dateOnly(classification.effective_date),
      source_id: classificationRow.source_id,
      source_url: classification.source_url || classificationRow.source_url,
    } : null,
  };
  const dividendYield = yieldPayload.values?.dividendYield;
  const secYield = yieldPayload.values?.secYield;
  result._field_provenance = {
    summary: snapshotMeta(latestSnapshot(snapshots, 'summary')),
    performance: snapshotMeta(ytdRow), expense_ratio_history: snapshotMeta(expense),
    aum_history: snapshotMeta(aum), nav: latestNav ? { source_id: latestNav.source_id,
      source_url: latestNav.source_url, valuation_date: latestNav.valuation_date } : null,
    yield_candidates: yieldRow ? { source: snapshotMeta(yieldRow), dividend_yield: dividendYield || null,
      sec_yield: secYield || null, note: 'Yield bases are kept explicit; neither is silently substituted for a generic yield.' } : null,
    classification: snapshotMeta(classificationRow),
  };
  result._missing_fields = ['min_investment', 'turnover_rate', 'yield', 'expense_ratio_net', 'category']
    .filter((field) => result[field] === null);
  return result;
}

function buildPerformance(snapshots) {
  const rows = snapshots.get('performance') || [];
  if (!rows.length) return null;
  const trailing = new Map(); const annual = [];
  for (const row of rows) {
    const payload = safeJson(row.payload);
    if (payload.metric && numeric(payload.value) !== null) {
      const metric = String(payload.metric);
      const period = ({ oneYearReturn: '1_year', ytdReturn: 'ytd', CYTD: 'ytd', threeYearReturn: '3_year', fiveYearReturn: '5_year', tenYearReturn: '10_year', sinceInceptionReturn: 'since_inception' })[metric];
      if (period) trailing.set(period, { period, share_class_return: pctFraction(payload.value, payload), source_report_date: dateOnly(row.source_report_date), source_id: row.source_id, source_url: row.source_url });
    }
    for (const [rawPeriod, value] of Object.entries(payload.values || {})) {
      const period = ({ '1YR': '1_year', '3YR': '3_year', '5YR': '5_year', '10YR': '10_year', CYTD: 'ytd', ITD: 'since_inception' })[rawPeriod];
      if (period && numeric(value) !== null) trailing.set(period, { period, share_class_return: pctFraction(value, { ...payload, unit: payload.unit || 'percent' }), source_report_date: dateOnly(row.source_report_date), source_id: row.source_id, source_url: row.source_url });
    }
    if (Array.isArray(payload.trailing_returns)) for (const item of payload.trailing_returns) if (item?.period) trailing.set(item.period, item);
    if (Array.isArray(payload.annual_total_returns)) annual.push(...payload.annual_total_returns);
  }
  return { trailing_returns: [...trailing.values()], annual_total_returns: annual,
    quarterly_total_returns: [], methodology: 'Only publisher-reported performance values are included; source units and report dates are retained in each item. Category and load-adjusted returns are omitted unless explicitly published.',
    _missing_fields: ['category_return', 'rank_in_category', 'quarterly_total_returns', 'load_adjusted_returns'] };
}

function buildRisk(snapshots) {
  const rows = snapshots.get('risk') || [];
  if (!rows.length) return null;
  const measures = [];
  for (const row of rows) {
    const p = safeJson(row.payload);
    if (Array.isArray(p.volatility_measures)) measures.push(...p.volatility_measures);
    else if (p.metric && numeric(p.value) !== null) {
      const match = String(p.metric).match(/^(one|three|five|ten)_year_(.+)$/i);
      if (match) {
        const period = `${({ one: '1', three: '3', five: '5', ten: '10' })[match[1].toLowerCase()]}_year`;
        const field = ({ standard_deviation: 'std', beta: 'beta', alpha: 'alpha', sharpe_ratio: 'sharpe_ratio', treynor_ratio: 'treynor_ratio', r_squared: 'r_squared', mean_annual_return: 'mean_annual_return' })[match[2].toLowerCase()];
        if (field) measures.push({ period, [field]: numeric(p.value), source_report_date: dateOnly(row.source_report_date), source_id: row.source_id, source_url: row.source_url, unit: p.unit || null });
      }
    }
  }
  return measures.length ? { volatility_measures: measures, methodology: 'Source-reported risk metrics only; no ratings or category comparisons inferred.',
    _missing_metrics: ['alpha', 'beta', 'mean_annual_return', 'r_squared', 'std', 'sharpe_ratio', 'treynor_ratio', 'valuation_metrics', 'category_comparisons'] } : null;
}

function buildPurchaseInfo(fund, snapshots, navSeries) {
  const expenseRows = snapshots.get('expense_ratio_history') || [];
  const feeRows = snapshots.get('fees') || [];
  const purchase = snapshotPayload(snapshots, 'purchase_info');
  if (!expenseRows.length && !feeRows.length && !navSeries.length && !Object.keys(purchase).length) return null;
  const sorted = [...navSeries].sort((a, b) => String(a.valuation_date).localeCompare(String(b.valuation_date)));
  const pricing = {};
  if (sorted.length) {
    pricing.nav = numeric(sorted.at(-1).nav);
    pricing.nav_date = sorted.at(-1).valuation_date;
    const cutoff = new Date(`${String(sorted.at(-1).valuation_date).slice(0,10)}T00:00:00Z`);
    cutoff.setUTCDate(cutoff.getUTCDate() - 365);
    const year = sorted.filter((row) => new Date(`${String(row.valuation_date).slice(0,10)}T00:00:00Z`) >= cutoff).map((row) => numeric(row.nav)).filter((n) => n !== null);
    if (year.length) { pricing['12_month_low'] = Math.min(...year); pricing['12_month_high'] = Math.max(...year); }
    const latestDate = String(sorted.at(-1).valuation_date).slice(0, 10);
    const monthStart = new Date(`${latestDate.slice(0,7)}-01T00:00:00Z`);
    monthStart.setUTCMonth(monthStart.getUTCMonth() - 1);
    const prevMonth = sorted.filter((row) => new Date(`${String(row.valuation_date).slice(0,10)}T00:00:00Z`) < new Date(`${latestDate.slice(0,7)}-01T00:00:00Z`) && new Date(`${String(row.valuation_date).slice(0,10)}T00:00:00Z`) >= monthStart);
    if (prevMonth.length) { pricing.last_month = numeric(prevMonth.at(-1).nav); pricing.last_month_date = prevMonth.at(-1).valuation_date; }
    pricing.basis = 'Observed FundFlow NAVs within the stored trailing 365-day window; completeness is not guaranteed.';
  }
  const values = expenseRows.map((row) => ({ reported_value: row.payload?.reported_value ?? null,
    unit: row.payload?.unit ?? null, measure: row.payload?.measure ?? null,
    effective_date: row.payload?.effective_date ?? row.source_report_date ?? null,
    source_id: row.source_id, source_url: row.source_url }));
  return { expenses: purchase.expenses || feeRows.at(-1)?.payload || { source_reported_expense_ratios: values },
    minimums: purchase.minimums || null, pricing: { ...pricing, ...(purchase.pricing || {}) },
    brokerages: purchase.brokerages || null,
    _missing_fields: ['minimums', 'brokerages'].filter((field) => !purchase[field]),
    _note: 'Observed NAV ranges use only stored observations and may not be complete. Purchase minimums and brokerages are null unless a source explicitly reports them.' };
}

async function buildComposition(pool, fund, snapshots) {
  const stored = latestSnapshot(snapshots, 'composition');
  const sectorRow = latestSnapshot(snapshots, 'sector_allocation');
  const allocationRow = latestSnapshot(snapshots, 'asset_allocation');
  const assetAllocation = (allocationRow?.payload?.allocation || []).map((item) => ({
    asset_class: item.asset_class || item.code, code: item.code || null,
    weight_pct: numeric(item.weight_pct),
  })).filter((item) => item.asset_class && item.weight_pct !== null);
  const sectors = (sectorRow?.payload?.allocation || []).map((item) => ({
    sector: item.sector, weight: numeric(item.weight_pct ?? item.pct_of_nav),
    report_date: item.report_date || dateOnly(sectorRow.source_report_date), source_id: sectorRow.source_id,
  })).filter((item) => item.sector && item.weight !== null);
  if (stored) return { payload: stored.payload, provenance: snapshotMeta(stored) };
  const { rows } = await pool.query(`
    SELECT h.reporting_date::text AS reporting_date,h.security_name,h.ticker,h.isin,h.cusip,h.portfolio_weight,
      h.market_value,h.market_value_currency,h.data_source,h.source_url
    FROM portfolio_holdings h WHERE h.fund_id=$1
      AND h.reporting_date=(SELECT max(reporting_date) FROM portfolio_holdings WHERE fund_id=$1)
    ORDER BY h.portfolio_weight DESC NULLS LAST,h.market_value DESC NULLS LAST,h.holding_index
    LIMIT 20
  `, [fund.id]);
  if (!rows.length && !sectors.length && !assetAllocation.length) return null;
  return { payload: { top_holdings: rows.map((h) => ({ symbol: h.ticker, name: h.security_name,
    weight: numeric(h.portfolio_weight), isin: h.isin, cusip: h.cusip })),
    asset_allocation: assetAllocation.length ? assetAllocation : null,
    major_market_sectors: sectors.length ? sectors : null,
    _report_date: rows[0]?.reporting_date || dateOnly(sectorRow?.source_report_date), _scope: 'Filed portfolio holdings; FundFlow preserves whether the filing is series-level or fund-level.',
    _missing_fields: [...(sectors.length ? [] : ['major_market_sectors']),
      ...(assetAllocation.length ? [] : ['asset_allocation']), 'bond_breakdown'] },
    provenance: rows[0] ? { source_id: rows[0].data_source, source_url: rows[0].source_url, report_date: rows[0].reporting_date }
      : snapshotMeta(allocationRow || sectorRow) };
}

router.get('/list', async (req, res, next) => {
  try {
    if (req.query.figi) return res.status(422).json({ code: 422, message: 'FIGI lookup is not available: FundFlow has no verified FIGI mapping yet' });
    const page = Number(req.query.page || 1); const outputsize = Number(req.query.outputsize || 100);
    if (!Number.isInteger(page) || page < 1 || !Number.isInteger(outputsize) || outputsize < 1 || outputsize > 1000) {
      return res.status(400).json({ code: 400, message: 'page must be positive and outputsize must be between 1 and 1000' });
    }
    const values = []; const where = ["(f.fund_type IS NULL OR f.fund_type NOT ILIKE '%ETF%')"];
    const add = (sql, value) => { values.push(value); where.push(sql.replace('?', `$${values.length}`)); };
    if (req.query.symbol) add('upper(f.ticker)=upper(?)', req.query.symbol);
    if (req.query.isin) add('upper(f.isin)=upper(?)', req.query.isin);
    if (req.query.cusip) add("EXISTS (SELECT 1 FROM fund_profile_snapshots cp WHERE cp.fund_id=f.id AND cp.dataset IN ('summary','identifiers') AND upper(cp.payload->>'cusip')=upper(?))", req.query.cusip);
    if (req.query.cik) add('f.sec_cik=?', String(req.query.cik).replace(/^0+/, ''));
    if (req.query.country) add('f.domicile_country=?', toAlpha2(req.query.country));
    if (req.query.fund_family) add('f.provider ILIKE ?', `%${req.query.fund_family}%`);
    if (req.query.fund_type) add('f.fund_type ILIKE ?', `%${req.query.fund_type}%`);
    for (const field of ['performance_rating', 'risk_rating']) {
      if (req.query[field] !== undefined) {
        const score = Number(req.query[field]);
        if (!Number.isInteger(score) || score < 0 || score > 5) return res.status(400).json({ code: 400, message: `${field} must be an integer from 0 to 5` });
        add(`EXISTS (SELECT 1 FROM fund_profile_snapshots r WHERE r.fund_id=f.id AND r.dataset='ratings' AND r.payload->>'${field}'=?)`, String(score));
      }
    }
    const filter = `WHERE ${where.join(' AND ')}`;
    const count = await req.app.locals.pool.query(`SELECT count(DISTINCT f.id)::int AS total FROM funds f ${filter}`, values);
    const offset = (page - 1) * outputsize;
    const { rows } = await req.app.locals.pool.query(`
      SELECT f.id,f.ticker,f.name,f.domicile_country,f.provider,f.fund_type,
        f.currency,f.inception_date,f.net_assets,f.isin,f.sec_cik,
        summary.payload AS summary_payload,market.payload AS market_payload,
        ratings.payload AS ratings_payload
      FROM funds f
      LEFT JOIN LATERAL (SELECT payload FROM fund_profile_snapshots WHERE fund_id=f.id AND dataset='summary' ORDER BY retrieved_at DESC,id DESC LIMIT 1) summary ON true
      LEFT JOIN LATERAL (SELECT payload FROM fund_profile_snapshots WHERE fund_id=f.id AND dataset='market_data_metadata' ORDER BY retrieved_at DESC,id DESC LIMIT 1) market ON true
      LEFT JOIN LATERAL (SELECT payload FROM fund_profile_snapshots WHERE fund_id=f.id AND dataset='ratings' ORDER BY retrieved_at DESC,id DESC LIMIT 1) ratings ON true
      ${filter}
      ORDER BY f.net_assets DESC NULLS LAST,f.id
      LIMIT $${values.length + 1} OFFSET $${values.length + 2}
    `, [...values, outputsize, offset]);
    const list = rows.map((r) => {
      const s = safeJson(r.summary_payload); const m = safeJson(r.market_payload); const rating = safeJson(r.ratings_payload);
      return {
        symbol: r.ticker || pick(s, 'symbol', 'ticker'), name: r.name,
        country: countryName(r.domicile_country), fund_family: r.provider || pick(s, 'fund_family', 'family'),
        fund_type: r.fund_type || pick(s, 'fund_type', 'category'),
        performance_rating: pick(rating, 'performance_rating'), risk_rating: pick(rating, 'risk_rating'),
        currency: r.currency || pick(s, 'currency'), exchange: pick(m, 'exchange'), mic_code: pick(m, 'mic_code'),
      };
    });
    if (String(req.query.format || 'JSON').toUpperCase() === 'CSV') {
      const delimiter = String(req.query.delimiter || ';').slice(0, 4);
      const keys = ['symbol','name','country','fund_family','fund_type','performance_rating','risk_rating','currency','exchange','mic_code'];
      const quote = (v) => `"${String(v ?? '').replaceAll('"','""')}"`;
      return res.type('text/csv').send([keys.join(delimiter), ...list.map((row) => keys.map((key) => quote(row[key])).join(delimiter))].join('\n'));
    }
    res.json({ result: { count: count.rows[0].total, list }, status: 'ok', _fundflow: { page, outputsize, provenance: 'FundFlow source records; absent values are null' } });
  } catch (error) { next(error); }
});

router.get('/family', async (req, res, next) => {
  try {
    const values = []; const predicates = [];
    if (req.query.country) { values.push(toAlpha2(req.query.country)); predicates.push(`f.domicile_country=$${values.length}`); }
    if (req.query.fund_family) { values.push(`%${req.query.fund_family}%`); predicates.push(`f.provider ILIKE $${values.length}`); }
    const where = predicates.length ? `WHERE ${predicates.join(' AND ')}` : '';
    const { rows } = await req.app.locals.pool.query(`SELECT f.domicile_country, array_agg(DISTINCT f.provider ORDER BY f.provider) FILTER (WHERE f.provider IS NOT NULL AND f.provider<>'') AS items FROM funds f ${where} GROUP BY f.domicile_country`, values);
    const result = Object.fromEntries(rows.map((r) => [countryName(r.domicile_country), r.items || []]));
    res.json({ result, status: 'ok', _fundflow: { provenance: 'Distinct provider values in source-backed FundFlow records' } });
  } catch (error) { next(error); }
});

router.get('/type', async (req, res, next) => {
  try {
    const values = []; const predicates = [];
    if (req.query.country) { values.push(toAlpha2(req.query.country)); predicates.push(`f.domicile_country=$${values.length}`); }
    if (req.query.fund_type) { values.push(`%${req.query.fund_type}%`); predicates.push(`f.fund_type ILIKE $${values.length}`); }
    const where = predicates.length ? `WHERE ${predicates.join(' AND ')}` : '';
    const { rows } = await req.app.locals.pool.query(`SELECT f.domicile_country, array_agg(DISTINCT f.fund_type ORDER BY f.fund_type) FILTER (WHERE f.fund_type IS NOT NULL AND f.fund_type<>'') AS items FROM funds f ${where} GROUP BY f.domicile_country`, values);
    const result = Object.fromEntries(rows.map((r) => [countryName(r.domicile_country), r.items || []]));
    res.json({ result, status: 'ok', _fundflow: { provenance: 'Distinct source-reported fund_type values; not reclassified to Twelve Data categories' } });
  } catch (error) { next(error); }
});

async function getFund(req, res) {
  const { symbol, isin, cusip } = req.query;
  if (req.query.figi) { res.status(422).json({ code: 422, message: 'FIGI lookup is not available: FundFlow has no verified FIGI mapping yet' }); return null; }
  if (![symbol, isin, cusip].some(Boolean)) return res.status(400).json({ code: 400, message: 'One of symbol, isin, or cusip is required' });
  const values = []; const predicates = [];
  if (symbol) { values.push(symbol); predicates.push(`upper(f.ticker)=upper($${values.length})`); }
  if (isin) { values.push(isin); predicates.push(`upper(f.isin)=upper($${values.length})`); }
  if (cusip) { values.push(cusip); predicates.push(`EXISTS(SELECT 1 FROM fund_profile_snapshots c WHERE c.fund_id=f.id AND c.dataset IN ('summary','identifiers') AND upper(c.payload->>'cusip')=upper($${values.length}))`); }
  const { rows } = await req.app.locals.pool.query(`SELECT f.* FROM funds f WHERE ${predicates.join(' OR ')} ORDER BY f.id LIMIT 2`, values);
  if (!rows.length) { res.status(404).json({ code: 404, message: 'Fund not found in FundFlow source records' }); return null; }
  if (rows.length > 1 && !isin && !cusip) { res.status(409).json({ code: 409, message: 'Ticker is ambiguous across FundFlow share classes; query by ISIN or CUSIP' }); return null; }
  const fund = rows[0];
  const snapshots = await profileRows(req.app.locals.pool, [fund.id]);
  const { rows: navSeries } = await req.app.locals.pool.query(`
    SELECT valuation_date::text AS valuation_date,nav,currency,source_id,source_url
    FROM nav_observations WHERE fund_id=$1 AND nav > 0 AND COALESCE(source_id,'') NOT ILIKE '%yahoo%'
    ORDER BY valuation_date DESC,retrieved_at DESC,id DESC LIMIT 1500
  `, [fund.id]);
  return { fund, snapshots: snapshots.get(fund.id) || new Map(), navSeries };
}

async function sectionPayload(pool, section, fund, snapshots, navSeries) {
  if (section === 'summary') return buildSummary(fund, snapshots, navSeries[0] || null);
  if (section === 'performance') return buildPerformance(snapshots);
  if (section === 'risk') return buildRisk(snapshots);
  if (section === 'ratings') {
    const row = latestSnapshot(snapshots, 'ratings');
    return row ? row.payload : null;
  }
  if (section === 'composition') return buildComposition(pool, fund, snapshots);
  if (section === 'purchase_info') return buildPurchaseInfo(fund, snapshots, navSeries);
  if (section === 'sustainability') {
    const row = latestSnapshot(snapshots, 'sustainability');
    return row ? row.payload : null;
  }
  return null;
}

router.get('/world', async (req, res, next) => {
  try {
    const found = await getFund(req, res); if (!found) return;
    const { fund, snapshots, navSeries } = found;
    const mutual_fund = {};
    const provenance = {};
    for (const [section, dataset] of Object.entries(datasetForSection)) {
      const value = await sectionPayload(req.app.locals.pool, section, fund, snapshots, navSeries);
      if (value !== null && value !== undefined) {
        mutual_fund[section] = value.payload === undefined ? value : value.payload;
        provenance[section] = value.provenance || snapshotMeta(latestSnapshot(snapshots, dataset)) || null;
      }
    }
    const missing_sections = [...profileSections].filter((section) => !mutual_fund[section]);
    res.json({ mutual_fund, status: 'partial', _fundflow: { fund_id: fund.id, provenance, missing_sections,
      note: 'FundFlow does not claim parity with all Twelve Data fields or measurement conventions.' } });
  } catch (error) { next(error); }
});

for (const section of profileSections) {
  router.get(`/world/${section}`, async (req, res, next) => {
    try {
      const found = await getFund(req, res); if (!found) return;
      const { fund, snapshots, navSeries } = found;
      const value = await sectionPayload(req.app.locals.pool, section, fund, snapshots, navSeries);
      if (value === null || value === undefined) return res.status(404).json({ code: 404, message: `No source-backed ${section} record is available in FundFlow`, status: 'data_unavailable', _fundflow: { fund_id: fund.id, dataset: datasetForSection[section] } });
      const payload = value.payload === undefined ? value : value.payload;
      const provenance = value.provenance || snapshotMeta(latestSnapshot(snapshots, datasetForSection[section])) || null;
      res.json({ mutual_fund: { [section]: payload }, status: 'partial', _fundflow: { fund_id: fund.id, provenance,
        note: 'FundFlow returns only source-backed fields and does not claim parity with all Twelve Data fields or measurement conventions.' } });
    } catch (error) { next(error); }
  });
}

module.exports = router;
