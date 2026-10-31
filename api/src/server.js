require('dotenv').config({ path: require('node:path').resolve(__dirname, '../.env') });
require('dotenv').config({ path: require('node:path').resolve(__dirname, '../../.env') });
const { createApp } = require('./app');
const { createPool } = require('./db/pool');
const { port } = require('./config');
const { terminateChildren } = require('./services/etlRunner');
const { waitForRuns, recoverStaleRuns } = require('./services/runStore');

async function main() {
  const pool = createPool();
  await pool.query('SELECT 1');
  await recoverStaleRuns(pool);
  const app = createApp({ pool });
  const server = app.listen(port, () => console.log(JSON.stringify({ level: 'info', message: 'API listening', port })));
  let shuttingDown = false;
  const shutdown = () => {
    if (shuttingDown) return;
    shuttingDown = true;
    server.close(async () => { await terminateChildren(); await waitForRuns(); await pool.end(); process.exit(0); });
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((error) => { console.error(JSON.stringify({ level: 'error', message: 'API failed to start', error: error.message })); process.exit(1); });
