const express = require('express');
const { randomUUID } = require('node:crypto');
const { z } = require('zod');
const { rateLimit } = require('express-rate-limit');
const { requireAdmin } = require('../middleware/admin');
const { active, scheduleRun } = require('../services/runStore');
const { runnableSources } = require('../services/catalog');
const router = express.Router();
const runLimit = rateLimit({ windowMs: 60_000, limit: 5, standardHeaders: true, legacyHeaders: false });
const requestSchema = z.object({ all: z.boolean().optional(), sourceIds: z.array(z.string().min(1).max(100)).max(100).optional(), countryCodes: z.array(z.string().length(2)).max(250).optional() }).strict();

router.post('/runs', runLimit, requireAdmin, async (req, res, next) => {
  const parsed = requestSchema.safeParse(req.body || {});
  if (!parsed.success) return res.status(400).json({ error: { code: 'INVALID_REQUEST', message: parsed.error.issues.map((e) => e.message).join('; ') } });
  const { all = false, sourceIds = [], countryCodes = [] } = parsed.data;
  const { entries } = require('../services/catalog');
  let selected = all ? [...runnableSources] : [...sourceIds];
  if (countryCodes.length) {
    const codes = new Set(countryCodes.map((v) => v.toUpperCase()));
    selected = [...new Set([...selected, ...[...entries.values()].filter((r) => codes.has(r.country_code) && runnableSources.has(r.source_id)).map((r) => r.source_id)])];
  }
  selected = [...new Set(selected)];
  if (!selected.length) return res.status(400).json({ error: { code: 'NO_SOURCES_SELECTED', message: 'Choose one or more configured ETL sources or set all=true' } });
  if (selected.some((id) => !runnableSources.has(id))) return res.status(400).json({ error: { code: 'UNKNOWN_SOURCE', message: 'One or more source IDs are not registered Python ETL connectors' } });
  if (active.size) return res.status(409).json({ error: { code: 'ETL_ALREADY_RUNNING', message: 'An ETL run is already active' } });
  const id = randomUUID();
  // Reserve synchronously before the database await so concurrent requests on
  // this process cannot both pass the active-run check.
  active.add(id);
  try {
    await req.app.locals.pool.query('INSERT INTO api_etl_runs(id,status,source_ids) VALUES($1,\'queued\',$2::jsonb)', [id, JSON.stringify(selected)]);
    scheduleRun(req.app.locals.pool, id, selected, req.app.locals.etlLauncher);
    res.status(202).json({ data: { id, status: 'queued', sourceIds: selected, requestedAt: new Date().toISOString() } });
  } catch (error) {
    active.delete(id);
    if (error.code === '23505' && error.constraint === 'uq_api_etl_runs_single_active') {
      return res.status(409).json({ error: { code: 'ETL_ALREADY_RUNNING', message: 'An ETL run is already active' } });
    }
    next(error);
  }
});

module.exports = router;
