require('dotenv').config({ path: require('node:path').resolve(__dirname, '../.env') });
require('dotenv').config({ path: require('node:path').resolve(__dirname, '../../.env') });
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { rateLimit } = require('express-rate-limit');
const health = require('./routes/health');
const catalog = require('./routes/catalog');
const sourceChecks = require('./routes/sourceChecks');
const funds = require('./routes/funds');
const dashboard = require('./routes/dashboard');
const etl = require('./routes/etl');
const { notFound, errorHandler } = require('./middleware/errors');

function createApp({ pool, etlLauncher } = {}) {
  const app = express();
  app.locals.pool = pool || require('./db/pool').pool;
  app.locals.etlLauncher = etlLauncher || require('./services/runStore').launchRun;
  app.disable('x-powered-by');
  app.use(helmet());
  app.use(cors({ origin: process.env.FRONTEND_ORIGIN || 'http://localhost:5173', methods: ['GET','POST'], allowedHeaders: ['Content-Type','X-API-Key'] }));
  app.use(express.json({ limit: '32kb' }));
  app.get('/health', (_req, res) => res.json({ status: 'ok', version: require('../package.json').version }));
  app.use('/api/v1/health', health);
  app.use('/api/v1', catalog);
  app.use('/api/v1', sourceChecks);
  app.use('/api/v1/funds', funds.router);
  app.use('/api/v1', dashboard);
  app.use('/api/v1/etl', etl);
  app.use(notFound);
  app.use(errorHandler);
  return app;
}

module.exports = { createApp };
