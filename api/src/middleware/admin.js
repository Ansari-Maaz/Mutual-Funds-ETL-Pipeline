const { adminApiKey } = require('../config');

function requireAdmin(req, res, next) {
  const expected = process.env.ADMIN_API_KEY || adminApiKey;
  if (!expected) return res.status(503).json({ error: { code: 'ADMIN_KEY_NOT_CONFIGURED', message: 'ETL controls are disabled until ADMIN_API_KEY is configured' } });
  const supplied = req.get('x-api-key') || '';
  const a = Buffer.from(supplied);
  const b = Buffer.from(expected);
  const valid = a.length === b.length && require('node:crypto').timingSafeEqual(a, b);
  if (!valid) return res.status(401).json({ error: { code: 'UNAUTHORIZED', message: 'A valid X-API-Key header is required' } });
  next();
}

module.exports = { requireAdmin };
