const express = require('express');
const { URL } = require('node:url');
const { rateLimit } = require('express-rate-limit');
const { requireAdmin } = require('../middleware/admin');
const router = express.Router();
const checkLimit = rateLimit({ windowMs: 60_000, limit: 12, standardHeaders: true, legacyHeaders: false });

router.post('/sources/:id/check', checkLimit, requireAdmin, async (req, res, next) => {
  let source;
  try {
    const { rows } = await req.app.locals.pool.query('SELECT * FROM sources WHERE source_id=$1', [req.params.id]);
    source = rows[0];
    if (!source) return res.status(404).json({ error: { code: 'SOURCE_NOT_FOUND', message: 'Source not found' } });
    const { entries } = require('../services/catalog');
    const catalog = entries.get(source.source_id);
    if (!source.endpoint_url || !catalog?.official_website) {
      return res.status(422).json({ error: { code: 'SOURCE_ENDPOINT_MISSING', message: 'This source has no registered HTTP endpoint to check' } });
    }
    let target; let official;
    try { target = new URL(source.endpoint_url); official = new URL(catalog.official_website); }
    catch { return res.status(422).json({ error: { code: 'SOURCE_ENDPOINT_INVALID', message: 'The registered source endpoint is not a valid URL' } }); }
    if (target.protocol !== 'https:' || (target.port && target.port !== '443') || !official.hostname || target.hostname !== official.hostname) {
      return res.status(422).json({ error: { code: 'SOURCE_URL_NOT_ALLOWLISTED', message: 'Source URL is not an HTTPS endpoint on its registered official host' } });
    }
    const started = Date.now();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    let result;
    try {
      const response = await fetch(target, { method: 'HEAD', redirect: 'manual', signal: controller.signal, headers: { 'User-Agent': 'MF-ETL-SourceCheck/1.0' } });
      result = { status: response.status >= 200 && response.status < 400 ? 'reachable' : response.status === 429 ? 'rate_limited' : 'unavailable', httpStatus: response.status, responseTimeMs: Date.now() - started, message: response.status >= 400 ? `Official endpoint responded with HTTP ${response.status}` : null };
    } catch (error) {
      result = { status: 'unavailable', httpStatus: null, responseTimeMs: Date.now() - started, message: error.name === 'AbortError' ? 'Source check timed out after 8 seconds' : error.message };
    } finally { clearTimeout(timer); }
    await req.app.locals.pool.query('INSERT INTO api_source_checks(source_id,status,http_status,response_time_ms,error) VALUES($1,$2,$3,$4,$5)', [source.source_id, result.status, result.httpStatus, result.responseTimeMs, result.message]);
    res.status(result.status === 'unavailable' ? 502 : 200).json({ data: { sourceId: source.source_id, ...result, note: 'Connectivity only; this does not validate the source format or confirm a successful ETL load.' } });
  } catch (error) { next(error); }
});

module.exports = router;
