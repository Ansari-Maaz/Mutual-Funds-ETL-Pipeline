const express = require('express');
const router = express.Router();

router.get('/countries', async (req, res, next) => {
  try {
    const { rows } = await req.app.locals.pool.query(`
      SELECT s.country_code AS code, COUNT(DISTINCT s.source_id)::int AS source_count,
             COUNT(DISTINCT f.id)::int AS fund_count,
             COUNT(DISTINCT CASE WHEN f.id IS NOT NULL THEN s.source_id END)::int AS ingested_source_count,
             COUNT(DISTINCT n.id)::int AS nav_count
      FROM sources s LEFT JOIN funds f ON f.source_id=s.source_id
      LEFT JOIN nav_observations n ON n.fund_id=f.id GROUP BY s.country_code ORDER BY s.country_code`);
    const { countries } = require('../services/catalog');
    res.json({ data: rows.map((row) => ({ ...countries.get(row.code), ...row, ingestionStatus: Number(row.fund_count) ? 'integrated' : 'not_integrated' })) });
  } catch (error) { next(error); }
});

router.get('/sources', async (req, res, next) => {
  try {
    const { rows } = await req.app.locals.pool.query(`
      SELECT s.source_id,s.country_code,s.organization,s.source_name,s.endpoint_url,s.verification_status,s.integration_status,s.license_status,
        (SELECT row_to_json(c) FROM (SELECT checked_at,status,http_status,response_time_ms,error FROM api_source_checks WHERE source_id=s.source_id ORDER BY checked_at DESC LIMIT 1)c) AS latest_check,
        (SELECT row_to_json(r) FROM (SELECT id,status,requested_at,finished_at,results,error FROM api_etl_runs WHERE source_ids @> jsonb_build_array(s.source_id) ORDER BY requested_at DESC LIMIT 1)r) AS latest_run,
        (SELECT count(*)::int FROM funds f WHERE f.source_id=s.source_id) AS fund_count,
        (SELECT count(*)::int FROM nav_observations n JOIN funds f ON f.id=n.fund_id WHERE f.source_id=s.source_id) AS nav_count
      FROM sources s ORDER BY s.country_code,s.source_id`);
    const { entries, countries, assignmentCountryCodes } = require('../services/catalog');
    res.json({ data: rows.map((row) => ({ ...entries.get(row.source_id), ...row,
      runnable: require('../services/catalog').runnableSources.has(row.source_id),
      assignmentScope: assignmentCountryCodes.has(row.country_code), country: countries.get(row.country_code) })) });
  } catch (error) { next(error); }
});

router.get('/sources/:id', async (req, res, next) => {
  try {
    const { rows } = await req.app.locals.pool.query('SELECT * FROM sources WHERE source_id=$1', [req.params.id]);
    if (!rows.length) return res.status(404).json({ error: { code: 'SOURCE_NOT_FOUND', message: 'Source not found' } });
    const { entries } = require('../services/catalog');
    const source = rows[0];
    res.json({ data: { ...entries.get(source.source_id), ...source } });
  } catch (error) { next(error); }
});

module.exports = router;
