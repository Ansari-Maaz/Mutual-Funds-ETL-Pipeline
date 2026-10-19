require('dotenv').config({ path: require('node:path').resolve(__dirname, '../.env') });
require('dotenv').config({ path: require('node:path').resolve(__dirname, '../../.env') });
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
require('../src/app'); // Loads the same environment configuration as the API server.
const { pool } = require('../src/db/pool');

async function main() {
  const root = path.resolve(__dirname, '../..');
  const sourceId = 'cvm_open_fund_data';
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'reports/cvm_dataset_manifest.json'), 'utf8'));
  assert(manifest.some((row) => row.url.startsWith('https://dados.cvm.gov.br/')), 'expected the official CVM source manifest');
  const latest = JSON.parse(fs.readFileSync(path.join(root, 'reports/latest_run.json'), 'utf8'));
  assert(latest.results.some((row) => row.source_id === sourceId && row.status === 'Succeeded'), 'latest Python run must contain a successful CVM connector result');

  const dbRecord = await pool.query(`SELECT f.id,f.name,f.domicile_country,f.currency,n.valuation_date,n.nav,n.currency AS nav_currency
    FROM funds f JOIN nav_observations n ON n.fund_id=f.id WHERE f.source_id=$1
    ORDER BY n.valuation_date DESC LIMIT 1`, [sourceId]);
  assert.equal(dbRecord.rowCount, 1, 'expected loaded NAV observations in PostgreSQL');
  const sourceCount = await pool.query('SELECT count(*)::int AS count FROM funds WHERE source_id=$1', [sourceId]);

  const base = process.env.API_BASE_URL || 'http://127.0.0.1:3001';
  const healthResponse = await fetch(`${base}/api/v1/health/database`);
  assert.equal(healthResponse.status, 200, 'Node API database health should be available');
  const fundsResponse = await fetch(`${base}/api/v1/funds?source=${sourceId}&limit=1`);
  assert.equal(fundsResponse.status, 200, 'Node API should list funds from the Python-loaded source');
  const fundsBody = await fundsResponse.json();
  assert.equal(fundsBody.pagination.total, sourceCount.rows[0].count);
  assert.equal(fundsBody.data.length, 1);

  const row = dbRecord.rows[0];
  const navResponse = await fetch(`${base}/api/v1/funds/${row.id}/nav?limit=1`);
  assert.equal(navResponse.status, 200, 'Node API should return stored NAV observations');
  const navBody = await navResponse.json();
  assert.equal(navBody.data[0].nav, String(row.nav));
  assert.equal(navBody.data[0].currency, row.nav_currency);
  console.log(JSON.stringify({ status: 'passed', source: manifest.find((item) => item.url.startsWith('https://dados.cvm.gov.br/')).url, pythonRun: latest.generated_at, fundRecordsInPostgres: fundsBody.pagination.total, checkedFundId: row.id, checkedNav: navBody.data[0] }));
}

main().catch((error) => { console.error(error); process.exitCode = 1; }).finally(() => pool.end());
