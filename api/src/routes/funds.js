const express = require('express');
const { z } = require('zod');
const router = express.Router();
const dateOnly = (value) => value == null ? null : value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10);
const listQuery = z.object({ page: z.coerce.number().int().min(1).max(1_000_000).default(1), limit: z.coerce.number().int().min(1).max(100).default(25), country: z.string().length(2).optional(), currency: z.string().length(3).optional(), q: z.string().max(200).optional(), category: z.string().max(100).optional(), fund_type: z.string().max(100).optional(), status: z.string().max(100).optional(), isin: z.string().max(20).optional(), has_nav: z.enum(['true','false']).optional(), sort: z.enum(['name','country','currency','retrieved_at']).default('name'), order: z.enum(['asc','desc']).default('asc') });
const jsonFund = (r) => ({
  id: r.id,
  sourceId: r.source_id,
  sourceFundId: r.source_fund_id,
  name: r.name,
  legalName: r.legal_name,
  country: r.domicile_country,
  currency: r.currency,
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
  retrievedAt: r.retrieved_at,
  source: r.source_organization ? { organization: r.source_organization, name: r.source_name, url: r.source_endpoint_url } : null,
  latestNav: r.latest_nav == null ? null : { value: r.latest_nav, date: dateOnly(r.latest_nav_date), currency: r.latest_nav_currency },
});

router.get('/', async (req, res, next) => {
  try {
    const parsed = listQuery.safeParse(req.query);
    if (!parsed.success) return res.status(400).json({ error: { code: 'INVALID_QUERY', message: parsed.error.issues.map((e) => `${e.path.join('.')}: ${e.message}`).join('; ') } });
    const { page, limit, country, currency, q, category, fund_type, status, isin, has_nav, sort, order } = parsed.data;
    const values = []; const where = [];
    for (const [field, value] of [['f.domicile_country', country], ['f.currency', currency], ['f.category', category], ['f.fund_type', fund_type], ['f.status', status]]) if (value) { values.push(value); where.push(`${field}=$${values.length}`); }
    if (q) { values.push(`%${q.replace(/[\\%_]/g, '\\$&')}%`); where.push(`f.name ILIKE $${values.length} ESCAPE '\\'`); }
    if (isin) { values.push(`%${isin.replace(/[\\%_]/g, '\\$&')}%`); where.push(`f.isin ILIKE $${values.length} ESCAPE '\\'`); }
    if (has_nav === 'true') where.push('EXISTS (SELECT 1 FROM nav_observations nav_filter WHERE nav_filter.fund_id=f.id)');
    if (has_nav === 'false') where.push('NOT EXISTS (SELECT 1 FROM nav_observations nav_filter WHERE nav_filter.fund_id=f.id)');
    const filter = where.length ? `WHERE ${where.join(' AND ')}` : '';
    const count = await req.app.locals.pool.query(`SELECT count(*)::int AS total FROM funds f ${filter}`, values);
    const sortColumn = { name: 'f.name', country: 'f.domicile_country', currency: 'f.currency', retrieved_at: 'f.retrieved_at' }[sort];
    const paginationValues = [...values, limit, (page - 1) * limit];
    const result = await req.app.locals.pool.query(`SELECT f.* FROM funds f ${filter} ORDER BY ${sortColumn} ${order.toUpperCase()} NULLS LAST, f.id LIMIT $${values.length + 1} OFFSET $${values.length + 2}`, paginationValues);
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
             latest.currency AS latest_nav_currency
      FROM funds f
      LEFT JOIN sources s ON s.source_id = f.source_id
      LEFT JOIN LATERAL (
        SELECT nav, valuation_date, currency
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
    const { rows } = await req.app.locals.pool.query(`SELECT id,fund_id,valuation_date,nav,currency,retrieved_at FROM nav_observations WHERE ${filters.join(' AND ')} ORDER BY valuation_date DESC LIMIT $${values.length}`, values);
    res.json({ data: rows, count: rows.length });
  } catch (error) { next(error); }
});

module.exports = { router, jsonFund };
