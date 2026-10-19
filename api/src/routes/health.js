const express = require('express');
const router = express.Router();

router.get('/', (_req, res) => res.json({ status: 'ok', version: require('../../package.json').version, timestamp: new Date().toISOString() }));
router.get('/database', async (req, res, next) => {
  try { await req.app.locals.pool.query('SELECT 1'); res.json({ status: 'ok', database: 'connected' }); }
  catch (error) { next(Object.assign(new Error('Database connection failed'), { statusCode: 503, code: 'DATABASE_UNAVAILABLE', cause: error })); }
});
router.get('/etl', async (req, res, next) => {
  try {
    const { rows } = await req.app.locals.pool.query(`
      SELECT id::text,status,requested_at,started_at,finished_at FROM api_etl_runs
      UNION ALL
      SELECT 'python-'||id::text, lower(status), started_at, started_at, finished_at FROM etl_runs
      ORDER BY requested_at DESC LIMIT 1`);
    res.json({ status: 'ok', latestRun: rows[0] || null });
  } catch (error) { next(error); }
});

module.exports = router;
