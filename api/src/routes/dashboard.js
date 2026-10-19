const express = require('express');
const router = express.Router();

router.get('/stats', async (req, res, next) => {
  try {
    const [funds, navs, countries, sources, latest, successful] = await Promise.all([
      req.app.locals.pool.query('SELECT count(*)::int AS total FROM funds'),
      req.app.locals.pool.query('SELECT count(*)::int AS total FROM nav_observations'),
      req.app.locals.pool.query('SELECT count(DISTINCT country_code)::int AS total FROM sources'),
      req.app.locals.pool.query('SELECT count(*)::int AS total, count(*) FILTER (WHERE integration_status=\'Integrated\')::int AS integrated FROM sources'),
      req.app.locals.pool.query(`SELECT id::text,status,requested_at,started_at,finished_at FROM api_etl_runs
        UNION ALL SELECT 'python-'||id::text, lower(status), started_at, started_at, finished_at FROM etl_runs
        ORDER BY requested_at DESC LIMIT 1`),
      req.app.locals.pool.query(`SELECT max(finished_at) AS last_successful_at FROM (
        SELECT finished_at FROM api_etl_runs WHERE status='succeeded'
        UNION ALL SELECT finished_at FROM etl_runs WHERE lower(status)='succeeded'
      ) successful_runs`),
    ]);
    res.json({ data: { totalFunds: funds.rows[0].total, navObservations: navs.rows[0].total, configuredCountries: countries.rows[0].total, registeredSources: sources.rows[0].total, integratedSources: sources.rows[0].integrated, latestRun: latest.rows[0] || null, lastSuccessfulRunAt: successful.rows[0].last_successful_at || null } });
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
