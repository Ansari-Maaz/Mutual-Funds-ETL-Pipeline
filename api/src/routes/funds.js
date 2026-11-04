const express = require('express');
const { z } = require('zod');
const router = express.Router();
const { toAlpha2, toAlpha3 } = require('../services/countryCodes');
// PostgreSQL DATE values are parsed by node-postgres as local-midnight Date
// objects. Use local calendar parts so ISO conversion cannot shift them back a day.
const dateOnly = (value) => value == null ? null : value instanceof Date
  ? `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  : String(value).slice(0, 10);
const listQuery = z.object({ page: z.coerce.number().int().min(1).max(1_000_000).default(1), limit: z.coerce.number().int().min(1).max(100).default(25), country: z.string().regex(/^[A-Z]{2,3}$/i).optional(), currency: z.string().length(3).optional(), q: z.string().max(200).optional(), category: z.string().max(100).optional(), fund_type: z.string().max(100).optional(), status: z.string().max(100).optional(), holdings_status: z.enum(['available','unavailable','not_checked']).optional(), isin: z.string().max(20).optional(), has_nav: z.enum(['true','false']).optional(), sort: z.enum(['name','country','currency','retrieved_at']).default('name'), order: z.enum(['asc','desc']).default('asc') });
const jsonFund = (r) => ({
  id: r.id,
  sourceId: r.source_id,
  sourceFundId: r.source_fund_id,
  name: r.name,
  legalName: r.legal_name,
  country: toAlpha3(r.domicile_country),
  currency: r.currency,
  currencyBasis: r.currency_basis || null,
  isin: r.isin,
  provider: r.provider,
  category: r.category,
  fundType: r.fund_type,
  inceptionDate: dateOnly(r.inception_date),
  status: r.status,
  officialUrl: r.official_url,
  ticker: r.ticker,
  manager: r.manager,
  administrator: r.administrator,
  netAssets: r.net_assets,
  netAssetsDate: dateOnly(r.net_assets_date),
  targetAudience: r.target_audience,
  holdingsStatus: r.holdings_status || 'not_checked',
  holdingsReportDate: dateOnly(r.holdings_report_date),
  retrievedAt: r.retrieved_at,
  source: r.source_organization ? { organization: r.source_organization, name: r.source_name, url: r.source_endpoint_url } : null,
  latestNav: r.latest_nav == null ? null : { value: r.latest_nav, date: dateOnly(r.latest_nav_date), currency: r.latest_nav_currency, open: r.latest_nav_open ?? null, high: r.latest_nav_high ?? null, low: r.latest_nav_low ?? null, close: r.latest_nav_close ?? null, ohlcBasis: r.latest_nav_ohlc_basis || null, sourceId: r.latest_nav_source_id || null, sourceUrl: r.latest_nav_source_url || null },
});

router.get('/', async (req, res, next) => {
  try {
    const parsed = listQuery.safeParse(req.query);
    if (!parsed.success) return res.status(400).json({ error: { code: 'INVALID_QUERY', message: parsed.error.issues.map((e) => `${e.path.join('.')}: ${e.message}`).join('; ') } });
    const { page, limit, country: requestedCountry, currency, q, category, fund_type, status, holdings_status, isin, has_nav, sort, order } = parsed.data;
    const country = requestedCountry ? toAlpha2(requestedCountry) : undefined;
    const values = []; const where = [];
    for (const [field, value] of [['f.domicile_country', country], ['f.currency', currency], ['f.category', category], ['f.fund_type', fund_type], ['f.status', status], ['f.holdings_status', holdings_status]]) if (value) { values.push(value); where.push(`${field}=$${values.length}`); }
    if (q) { values.push(`%${q.replace(/[\\%_]/g, '\\$&')}%`); where.push(`f.name ILIKE $${values.length} ESCAPE '\\'`); }
    if (isin) { values.push(`%${isin.replace(/[\\%_]/g, '\\$&')}%`); where.push(`f.isin ILIKE $${values.length} ESCAPE '\\'`); }
    if (has_nav === 'true') where.push('EXISTS (SELECT 1 FROM nav_observations nav_filter WHERE nav_filter.fund_id=f.id)');
    if (has_nav === 'false') where.push('NOT EXISTS (SELECT 1 FROM nav_observations nav_filter WHERE nav_filter.fund_id=f.id)');
    const filter = where.length ? `WHERE ${where.join(' AND ')}` : '';
    const count = await req.app.locals.pool.query(`SELECT count(*)::int AS total FROM funds f ${filter}`, values);
    const sortColumn = { name: 'f.name', country: 'f.domicile_country', currency: 'f.currency', retrieved_at: 'f.retrieved_at' }[sort];
    const paginationValues = [...values, limit, (page - 1) * limit];
    const result = await req.app.locals.pool.query(`
      SELECT f.id,f.source_id,f.source_fund_id,f.name,f.legal_name,f.domicile_country,
             f.currency,f.currency_basis,f.isin,f.provider,f.category,f.fund_type,
             f.inception_date,f.status,f.official_url,f.ticker,f.manager,f.administrator,
             f.net_assets,f.net_assets_date,f.target_audience,f.holdings_status,
             f.holdings_report_date,f.retrieved_at
      FROM funds f ${filter}
      ORDER BY ${sortColumn} ${order.toUpperCase()} NULLS LAST, f.id
      LIMIT $${values.length + 1} OFFSET $${values.length + 2}
    `, paginationValues);
    res.json({ data: result.rows.map(jsonFund), pagination: { page, limit, total: count.rows[0].total, pages: Math.ceil(count.rows[0].total / limit) } });
  } catch (error) { next(error); }
});

router.get('/:id', async (req, res, next) => {
  if (!/^\d+$/.test(req.params.id)) return res.status(400).json({ error: { code: 'INVALID_ID', message: 'Fund id must be a positive integer' } });
  try {
    const { rows } = await req.app.locals.pool.query(`
      SELECT f.*, s.organization AS source_organization, s.source_name,
             s.endpoint_url AS source_endpoint_url,
             latest.nav AS latest_nav, latest.valuation_date AS latest_nav_date,
             latest.currency AS latest_nav_currency,
             latest.open AS latest_nav_open,latest.high AS latest_nav_high,
             latest.low AS latest_nav_low,latest.close AS latest_nav_close,
             latest.ohlc_basis AS latest_nav_ohlc_basis,
             latest.source_id AS latest_nav_source_id,latest.source_url AS latest_nav_source_url
      FROM funds f
      LEFT JOIN sources s ON s.source_id = f.source_id
      LEFT JOIN LATERAL (
        SELECT nav, valuation_date, currency, open, high, low, close, ohlc_basis, source_id, source_url
        FROM nav_observations
        WHERE fund_id = f.id
        ORDER BY valuation_date DESC
        LIMIT 1
      ) latest ON true
      WHERE f.id=$1
    `, [Number(req.params.id)]);
    if (!rows.length) return res.status(404).json({ error: { code: 'FUND_NOT_FOUND', message: 'Fund not found' } });
    res.json({ data: jsonFund(rows[0]) });
  } catch (error) { next(error); }
});

router.get('/:id/nav', async (req, res, next) => {
  if (!/^\d+$/.test(req.params.id)) return res.status(400).json({ error: { code: 'INVALID_ID', message: 'Fund id must be a positive integer' } });
  const query = z.object({ from: z.string().date().optional(), to: z.string().date().optional(), limit: z.coerce.number().int().min(1).max(5000).default(1000) }).safeParse(req.query);
  if (!query.success) return res.status(400).json({ error: { code: 'INVALID_QUERY', message: 'Use valid from/to dates and a limit from 1 to 5000' } });
  try {
    const { from, to, limit } = query.data; const values = [Number(req.params.id)]; const filters = ['fund_id=$1'];
    if (from) { values.push(from); filters.push(`valuation_date >= $${values.length}`); }
    if (to) { values.push(to); filters.push(`valuation_date <= $${values.length}`); }
    values.push(limit);
    const { rows } = await req.app.locals.pool.query(`SELECT id,fund_id,valuation_date,nav,open,high,low,close,ohlc_basis,currency,source_id,source_url,retrieved_at FROM nav_observations WHERE ${filters.join(' AND ')} ORDER BY valuation_date DESC LIMIT $${values.length}`, values);
    res.json({ data: rows, count: rows.length });
  } catch (error) { next(error); }
});

router.get('/:id/profile-data', async (req, res, next) => {
  if (!/^\d+$/.test(req.params.id)) return res.status(400).json({ error: { code: 'INVALID_ID', message: 'Fund id must be a positive integer' } });
  const query = z.object({ dataset: z.string().min(1).max(40).optional(), source_id: z.string().min(1).max(100).optional(), limit: z.coerce.number().int().min(1).max(500).default(100) }).safeParse(req.query);
  if (!query.success) return res.status(400).json({ error: { code: 'INVALID_QUERY', message: 'Use a dataset/source_id and a limit from 1 to 500' } });
  try {
    const fundId = Number(req.params.id);
    const { rows: funds } = await req.app.locals.pool.query('SELECT id FROM funds WHERE id=$1', [fundId]);
    if (!funds.length) return res.status(404).json({ error: { code: 'FUND_NOT_FOUND', message: 'Fund not found' } });
    const values = [fundId]; const filters = ['p.fund_id=$1'];
    if (query.data.dataset) { values.push(query.data.dataset); filters.push(`p.dataset=$${values.length}`); }
    if (query.data.source_id) { values.push(query.data.source_id); filters.push(`p.source_id=$${values.length}`); }
    values.push(query.data.limit);
    const { rows } = await req.app.locals.pool.query(`
      SELECT p.id,p.dataset,p.source_id,p.source_report_date::text AS source_report_date,
             p.payload,p.source_url,p.retrieved_at,s.organization AS source_organization,s.source_name
      FROM fund_profile_snapshots p JOIN sources s ON s.source_id=p.source_id
      WHERE ${filters.join(' AND ')}
      ORDER BY p.source_report_date DESC NULLS LAST,p.retrieved_at DESC,p.id DESC
      LIMIT $${values.length}`, values);
    const { rows: datasets } = await req.app.locals.pool.query(
      'SELECT DISTINCT dataset FROM fund_profile_snapshots WHERE fund_id=$1 ORDER BY dataset', [fundId]);
    res.json({ data: rows, datasets: datasets.map((row) => row.dataset), status: rows.length ? 'available' : 'unavailable', count: rows.length });
  } catch (error) { next(error); }
});

router.get('/:id/completeness', async (req, res, next) => {
  if (!/^\d+$/.test(req.params.id)) return res.status(400).json({ error: { code: 'INVALID_ID', message: 'Fund id must be a positive integer' } });
  try {
    const fundId = Number(req.params.id);
    const { rows: funds } = await req.app.locals.pool.query(`
      SELECT id,domicile_country,name,legal_name,ticker,isin,currency,provider,category,fund_type,
             inception_date,status,official_url,manager,sec_cik,sec_series_id,holdings_status
      FROM funds WHERE id=$1`, [fundId]);
    if (!funds.length) return res.status(404).json({ error: { code: 'FUND_NOT_FOUND', message: 'Fund not found' } });
    const fund = funds[0];
    const [{ rows: navRows }, { rows: holdingRows }, { rows: snapshotRows }, { rows: summaryRows }] = await Promise.all([
      req.app.locals.pool.query('SELECT count(*)::int AS count,count(source_id)::int AS sourced_count,count(source_url)::int AS url_count,min(valuation_date)::text AS first_date,max(valuation_date)::text AS latest_date FROM nav_observations WHERE fund_id=$1', [fundId]),
      req.app.locals.pool.query('SELECT count(*)::int AS count,min(reporting_date)::text AS first_date,max(reporting_date)::text AS latest_date FROM portfolio_holdings WHERE fund_id=$1', [fundId]),
      req.app.locals.pool.query(`SELECT dataset,count(*)::int AS count,count(DISTINCT source_report_date)::int AS report_dates,count(DISTINCT COALESCE(payload->>'scope','unspecified'))::int AS scopes,min(source_report_date)::text AS first_date,max(source_report_date)::text AS latest_date FROM fund_profile_snapshots WHERE fund_id=$1 GROUP BY dataset`, [fundId]),
      req.app.locals.pool.query(`SELECT payload FROM fund_profile_snapshots WHERE fund_id=$1 AND dataset='summary' ORDER BY retrieved_at DESC,id DESC LIMIT 1`, [fundId]),
    ]);
    const snapshotByDataset = Object.fromEntries(snapshotRows.map((row) => [row.dataset, row]));
    const profileSummary = summaryRows[0]?.payload || {};
    const requiredFields = [
      ['name', fund.name], ['legal_name', fund.legal_name], ['ticker', fund.ticker],
      ['provider', fund.provider], ['category', fund.category || profileSummary.category],
      ['fund_type', fund.fund_type || profileSummary.instrument_type],
      ['share_class', profileSummary.share_class || profileSummary.shareClass],
      ['plan', profileSummary.plan], ['distribution_option', profileSummary.distribution_option || profileSummary.distributionOption],
      ['isin', fund.isin], ['cusip', profileSummary.cusip], ['sec_cik', fund.sec_cik],
      ['sec_series_id', fund.sec_series_id], ['currency', fund.currency],
      ['inception_date', fund.inception_date || profileSummary.inception_date],
      ['benchmark', profileSummary.benchmark || profileSummary.benchmark_name],
      ['fund_manager', fund.manager || profileSummary.fund_manager],
      ['co_managers', profileSummary.co_managers], ['administrator', fund.administrator],
      ['domicile', toAlpha3(fund.domicile_country)], ['exchange', profileSummary.exchange],
      ['mic_code', profileSummary.mic_code], ['exchange_timezone', profileSummary.exchange_timezone],
      ['official_url', fund.official_url || profileSummary.official_url],
      ['factsheet_url', profileSummary.factsheet_url], ['prospectus_url', profileSummary.prospectus_url],
      ['investment_objective', profileSummary.objective || profileSummary.investment_objective],
      ['management_style', profileSummary.management_style],
    ];
    const fields = requiredFields.map(([field, value]) => ({ field, status: value != null && value !== '' ? 'available' : 'requires_verification', ...(value != null ? { value } : {}) }));
    const makeDataset = (name, count, { notApplicable = false, confirmedUnavailable = false, statusOverride = null, firstDate = null, latestDate = null, note = null } = {}) => ({
      dataset: name,
      status: notApplicable ? 'not_applicable' : statusOverride || (count > 0 ? 'available' : confirmedUnavailable ? 'unavailable' : 'requires_verification'),
      records: count,
      firstReportDate: firstDate,
      latestReportDate: latestDate,
      note,
    });
    const nav = navRows[0]; const holdings = holdingRows[0];
    const profileDatasets = [
      ['aum_history', 'aum_history'], ['expense_ratio_history', 'expense_ratio_history'],
      ['performance', 'performance'], ['risk', 'risk'], ['yields', 'yields'], ['fees', 'fees'],
      ['distributions', 'distributions'], ['official_documents', 'official_documents'],
      ['composition', 'composition'], ['money_market_nav_history', 'nav_history'],
    ].map(([dataset, key]) => makeDataset(dataset, snapshotByDataset[key]?.count || 0, {
      statusOverride: snapshotByDataset[key]?.count ? 'partially_available' : null,
      firstDate: snapshotByDataset[key]?.first_date || null,
      latestDate: snapshotByDataset[key]?.latest_date || null,
      note: snapshotByDataset[key] ? (dataset === 'money_market_nav_history'
        ? 'SEC Form N-MFP covers money market funds only; currency is not provided, so values remain separate from canonical NAV observations.'
        : null) : 'No source-backed snapshots stored; source research is still required.',
    }));
    const datasets = [
      makeDataset('scheme_master', fields.filter((item) => item.status === 'available').length, { statusOverride: 'partially_available', note: 'Field presence is reported separately; present values are not a completeness claim.' }),
      makeDataset('daily_nav_history', nav.count, { statusOverride: nav.count ? 'partially_available' : null, firstDate: dateOnly(nav.first_date), latestDate: dateOnly(nav.latest_date), note: nav.count ? `${nav.sourced_count || 0} of ${nav.count} observations have a registered source ID; ${nav.url_count || 0} have a source URL. Source attribution does not by itself verify that a price is an official NAV or that history is complete.` : 'No NAV observations stored.' }),
      makeDataset('portfolio_holdings', holdings.count, { firstDate: dateOnly(holdings.first_date), latestDate: dateOnly(holdings.latest_date), confirmedUnavailable: fund.holdings_status === 'unavailable', note: 'Use actual reporting cadence; an available filing date does not imply monthly publication.' }),
      ...profileDatasets,
      makeDataset('amfi_code', 0, { notApplicable: fund.domicile_country === 'US', note: fund.domicile_country === 'US' ? 'AMFI identifiers are India-specific; use applicable SEC, CUSIP, ticker and ISIN identifiers.' : 'Requires country-specific research.' }),
      makeDataset('twelve_data_parity', 0, { note: process.env.TWELVE_DATA_API_KEY || process.env.TD_KEY ? 'A key is configured, but no comparison result has been stored for this fund.' : 'No Twelve Data API key is configured on this API server; configure one locally to run authenticated comparison.' }),
    ];
    const unresolved = fields.some((field) => field.status !== 'available') || datasets.some((dataset) => ['partially_available', 'requires_verification', 'extraction_failed'].includes(dataset.status));
    res.json({ data: { fundId, ticker: fund.ticker, country: toAlpha3(fund.domicile_country), status: unresolved ? 'incomplete' : 'complete', generatedAt: new Date().toISOString(), fields, datasets } });
  } catch (error) { next(error); }
});

router.get('/:id/holdings', async (req, res, next) => {
  if (!/^\d+$/.test(req.params.id)) return res.status(400).json({ error: { code: 'INVALID_ID', message: 'Fund id must be a positive integer' } });
  const query = z.object({ report_date: z.string().date().optional(), limit: z.coerce.number().int().min(1).max(5000).default(1000) }).safeParse(req.query);
  if (!query.success) return res.status(400).json({ error: { code: 'INVALID_QUERY', message: 'Use a valid report_date and a limit from 1 to 5000' } });
  try {
    const fundId = Number(req.params.id);
    const { rows: funds } = await req.app.locals.pool.query(`
      SELECT f.holdings_status,f.holdings_report_date,
             COALESCE(array_agg(DISTINCT h.reporting_date ORDER BY h.reporting_date DESC)
               FILTER (WHERE h.reporting_date IS NOT NULL), '{}'::date[]) AS report_dates
      FROM funds f
      LEFT JOIN portfolio_holdings h ON h.fund_id=f.id
      WHERE f.id=$1
      GROUP BY f.id
    `, [fundId]);
    if (!funds.length) return res.status(404).json({ error: { code: 'FUND_NOT_FOUND', message: 'Fund not found' } });
    const reportDates = (funds[0].report_dates || []).map(dateOnly);
    const reportDate = query.data.report_date || dateOnly(funds[0].holdings_report_date) || reportDates[0] || null;
    if (!reportDate) return res.json({ data: [], status: funds[0].holdings_status || 'not_checked', reportDate: null, reportDates, count: 0 });
    const { rows } = await req.app.locals.pool.query(`
      SELECT h.id,h.fund_id,h.reporting_date::text AS reporting_date,h.security_name,h.ticker,h.isin,h.cusip,
             h.quantity,h.market_value,h.market_value_currency AS currency,
             COALESCE(h.portfolio_weight,m.portfolio_weight) AS portfolio_weight,
             h.data_source,h.source_url,h.accession_number,
             CASE WHEN h.data_source='sec_edgar_nport' THEN 'SEC series-level; shared across share classes'
                  ELSE 'Publisher-reported fund scope' END AS data_scope,
             f.sec_series_id,
             m.first_bought_date,m.share_change_percentage,m.one_year_return,
             m.forward_pe,m.sector,m.data_source AS metrics_source,
             m.source_url AS metrics_source_url,m.as_of_date::text AS metrics_as_of_date,
             m.calculation_basis AS metrics_calculation_basis
      FROM portfolio_holdings h
      LEFT JOIN funds f ON f.id=h.fund_id
      LEFT JOIN LATERAL (
        SELECT first_bought_date,portfolio_weight,share_change_percentage,one_year_return,forward_pe,
               sector,data_source,source_url,as_of_date,calculation_basis
        FROM holding_metrics WHERE holding_id=h.id AND as_of_date=h.reporting_date
        ORDER BY retrieved_at DESC,id DESC LIMIT 1
      ) m ON true
      WHERE h.fund_id=$1 AND h.reporting_date=$2
      ORDER BY h.portfolio_weight DESC NULLS LAST,h.market_value DESC NULLS LAST,h.security_name
      LIMIT $3`, [fundId, reportDate, query.data.limit]);
    res.json({ data: rows, status: funds[0].holdings_status || 'not_checked', reportDate, reportDates, count: rows.length });
  } catch (error) { next(error); }
});

module.exports = { router, jsonFund };
