const express = require('express');
const router = express.Router();

router.get('/stats', async (req, res, next) => {
  try {
    const [funds, navs, assignmentCountries, sources, latest, successful, usCoverage] = await Promise.all([
      req.app.locals.pool.query('SELECT count(*)::int AS total FROM funds'),
      req.app.locals.pool.query('SELECT count(*)::int AS total FROM nav_observations WHERE nav > 0'),
      req.app.locals.pool.query("SELECT count(DISTINCT country_code)::int AS total FROM sources WHERE country_code <> 'ES'"),
      req.app.locals.pool.query('SELECT count(*)::int AS total, count(*) FILTER (WHERE integration_status=\'Integrated\')::int AS integrated FROM sources'),
      req.app.locals.pool.query(`SELECT id::text,status,requested_at,started_at,finished_at FROM api_etl_runs
        UNION ALL SELECT 'python-'||id::text, lower(status), started_at, started_at, finished_at FROM etl_runs
        ORDER BY requested_at DESC LIMIT 1`),
      req.app.locals.pool.query(`SELECT max(finished_at) AS last_successful_at FROM (
        SELECT finished_at FROM api_etl_runs WHERE status='succeeded'
        UNION ALL SELECT finished_at FROM etl_runs WHERE lower(status)='succeeded'
      ) successful_runs`),
      req.app.locals.pool.query(`
        WITH us AS (
          SELECT f.id,
                 EXISTS (SELECT 1 FROM nav_observations n WHERE n.fund_id = f.id AND n.nav > 0) AS has_nav,
                 EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id = f.id) AS has_holdings
          FROM funds f WHERE f.domicile_country = 'US'
        )
        SELECT count(*)::int AS total,
               count(*) FILTER (WHERE has_nav)::int AS with_nav,
               count(*) FILTER (WHERE has_holdings)::int AS with_holdings
        FROM us`),
    ]);
    const fundRecords = funds.rows[0].total;
    const us = usCoverage.rows[0] || { total: 0, with_nav: 0, with_holdings: 0 };
    res.json({ data: { fundRecords, totalFunds: fundRecords, navObservations: navs.rows[0].total, configuredCountries: assignmentCountries.rows[0].total, registeredSources: sources.rows[0].total, integratedSources: sources.rows[0].integrated, latestRun: latest.rows[0] || null, lastSuccessfulRunAt: successful.rows[0].last_successful_at || null, usFunds: us.total, usFundsWithNav: us.with_nav, usFundsWithHoldings: us.with_holdings } });
  } catch (error) { next(error); }
});

router.get('/coverage/us', async (req, res, next) => {
  try {
    const pool = req.app.locals.pool;
    const [coverage, fields, profiles, navGaps, holdingGaps, officialSources] = await Promise.all([
      pool.query(`
        WITH us AS (
          SELECT f.id, f.ticker,
                 EXISTS (SELECT 1 FROM nav_observations n WHERE n.fund_id = f.id AND n.nav > 0) AS has_nav,
                 EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id = f.id) AS has_holdings
          FROM funds f WHERE f.domicile_country = 'US'
        )
        SELECT count(*)::int AS total,
               count(*) FILTER (WHERE has_nav)::int AS with_nav,
               count(*) FILTER (WHERE has_holdings)::int AS with_holdings,
               count(*) FILTER (WHERE has_nav AND has_holdings)::int AS with_both,
               count(*) FILTER (WHERE NOT has_nav AND NOT has_holdings)::int AS with_neither,
               count(*) FILTER (WHERE NOT has_nav)::int AS missing_nav,
               count(*) FILTER (WHERE NOT has_holdings)::int AS missing_holdings,
               count(*) FILTER (WHERE NOT has_nav AND ticker IS NULL)::int AS missing_nav_no_ticker
        FROM us`),
      pool.query(`
        WITH st AS (
          SELECT fund_id, (payload->>'reported_in_window')::boolean AS reporting
          FROM fund_profile_snapshots WHERE dataset = 'filing_status')
        SELECT count(*)::int AS total,
               count(*) FILTER (WHERE st.reporting)::int AS reporting,
               count(*) FILTER (WHERE NOT COALESCE(st.reporting, false))::int AS dormant,
               count(ticker)::int AS ticker,
               count(isin)::int AS isin,
               count(inception_date)::int AS inception_date,
               count(category) FILTER (WHERE btrim(category) <> '')::int AS category,
               count(manager) FILTER (WHERE btrim(manager) <> '')::int AS manager,
               count(net_assets)::int AS net_assets,
               count(ticker) FILTER (WHERE st.reporting)::int AS reporting_ticker,
               count(isin) FILTER (WHERE st.reporting)::int AS reporting_isin,
               count(inception_date) FILTER (WHERE st.reporting)::int AS reporting_inception_date,
               count(category) FILTER (WHERE st.reporting AND btrim(category) <> '')::int AS reporting_category,
               count(manager) FILTER (WHERE st.reporting AND btrim(manager) <> '')::int AS reporting_manager,
               count(net_assets) FILTER (WHERE st.reporting)::int AS reporting_net_assets
        FROM funds f LEFT JOIN st ON st.fund_id = f.id
        WHERE f.domicile_country = 'US'`),
      pool.query(`
        SELECT count(*)::int AS total,
               count(*) FILTER (WHERE dataset = 'expense_ratio_history')::int AS expense_ratio,
               count(*) FILTER (WHERE dataset = 'performance')::int AS performance,
               count(*) FILTER (WHERE dataset = 'n1a_prospectus')::int AS objective_strategy,
               count(*) FILTER (WHERE dataset = 'sector_allocation')::int AS sector_allocation,
               count(*) FILTER (WHERE dataset = 'asset_allocation')::int AS asset_allocation,
               count(*) FILTER (WHERE dataset = 'classification')::int AS classification,
               count(*) FILTER (WHERE dataset = 'service_providers')::int AS service_providers,
               count(*) FILTER (WHERE dataset = 'aum_history')::int AS aum_history,
               count(*) FILTER (WHERE dataset = 'filing_status')::int AS filing_status,
               count(*) FILTER (WHERE dataset = 'n1a_inception')::int AS n1a_inception
        FROM (SELECT DISTINCT fund_id, dataset FROM fund_profile_snapshots
              WHERE fund_id IN (SELECT id FROM funds WHERE domicile_country = 'US')) d`),
      pool.query(`
        SELECT provider,
               count(*)::int AS missing,
               count(ticker)::int AS with_ticker,
               min(ticker) AS sample_ticker
        FROM funds f
        WHERE domicile_country = 'US'
          AND EXISTS (SELECT 1 FROM fund_profile_snapshots fs WHERE fs.fund_id = f.id
                      AND fs.dataset = 'filing_status' AND (fs.payload->>'reported_in_window')::boolean)
          AND NOT EXISTS (SELECT 1 FROM nav_observations n WHERE n.fund_id = f.id AND n.nav > 0)
        GROUP BY provider ORDER BY missing DESC LIMIT 12`),
      pool.query(`
        SELECT provider,
               count(*)::int AS missing,
               min(ticker) AS sample_ticker
        FROM funds f
        WHERE domicile_country = 'US'
          AND EXISTS (SELECT 1 FROM fund_profile_snapshots fs WHERE fs.fund_id = f.id
                      AND fs.dataset = 'filing_status' AND (fs.payload->>'reported_in_window')::boolean)
          AND NOT EXISTS (SELECT 1 FROM portfolio_holdings h WHERE h.fund_id = f.id)
        GROUP BY provider ORDER BY missing DESC LIMIT 12`),
      pool.query(`
        SELECT source_id, organization, source_name, endpoint_url, integration_status, verification_status
        FROM sources WHERE country_code = 'US'
        ORDER BY organization, source_id`),
    ]);
    res.json({ data: {
      generatedAt: new Date().toISOString(),
      coverage: coverage.rows[0],
      fields: fields.rows[0],
      profiles: profiles.rows[0],
      navGaps: navGaps.rows,
      holdingGaps: holdingGaps.rows,
      officialSources: officialSources.rows,
    } });
  } catch (error) { next(error); }
});

router.get('/etl/runs', async (req, res, next) => {
  const limit = Number(req.query.limit || 20);
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) return res.status(400).json({ error: { code: 'INVALID_QUERY', message: 'limit must be between 1 and 100' } });
  try {
    const { rows } = await req.app.locals.pool.query(`
      SELECT id::text,status,source_ids,requested_at,started_at,finished_at,exit_code,results,error FROM api_etl_runs
      UNION ALL
      SELECT 'python-'||id::text, lower(status), CASE WHEN source_id IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(source_id) END,
        started_at,started_at,finished_at,NULL,'[]'::jsonb,error FROM etl_runs
      ORDER BY requested_at DESC LIMIT $1`, [limit]);
    res.json({ data: rows });
  } catch (error) { next(error); }
});

router.get('/etl/runs/:id', async (req, res, next) => {
  try {
    let rows;
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(req.params.id)) {
      rows = (await req.app.locals.pool.query('SELECT * FROM api_etl_runs WHERE id=$1', [req.params.id])).rows;
    } else if (/^python-\d+$/.test(req.params.id)) {
      rows = (await req.app.locals.pool.query("SELECT 'python-'||id::text AS id, lower(status) AS status, CASE WHEN source_id IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(source_id) END AS source_ids, started_at AS requested_at, started_at, finished_at, records_extracted, records_loaded, error, '[]'::jsonb AS results FROM etl_runs WHERE id=$1", [Number(req.params.id.slice(7))])).rows;
    } else return res.status(400).json({ error: { code: 'INVALID_ID', message: 'Run id must be an API UUID or python run ID' } });
    if (!rows.length) return res.status(404).json({ error: { code: 'RUN_NOT_FOUND', message: 'ETL run not found' } });
    res.json({ data: rows[0] });
  } catch (error) { next(error); }
});

module.exports = router;
