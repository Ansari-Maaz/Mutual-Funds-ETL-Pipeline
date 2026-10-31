const { Pool } = require('pg');
const { databaseUrl } = require('../config');

function createPool(options = {}) {
  if (!databaseUrl) {
    throw new Error('DATABASE_URL is required. Configure the intended PostgreSQL database before starting the API.');
  }
  if (!/^postgres(?:ql)?:\/\//i.test(databaseUrl)) {
    throw new Error('DATABASE_URL must be a PostgreSQL connection URL.');
  }
  return new Pool({ connectionString: databaseUrl, max: 12, idleTimeoutMillis: 30000, connectionTimeoutMillis: 5000, ...options });
}

let sharedPool;
function getPool() {
  if (!sharedPool) sharedPool = createPool();
  return sharedPool;
}

module.exports = { get pool() { return getPool(); }, createPool };
