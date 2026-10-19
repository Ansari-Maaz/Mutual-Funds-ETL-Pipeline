const { Pool } = require('pg');
const { databaseUrl } = require('../config');

function createPool(options = {}) {
  return new Pool({ connectionString: databaseUrl, max: 12, idleTimeoutMillis: 30000, connectionTimeoutMillis: 5000, ...options });
}

module.exports = { pool: createPool(), createPool };
