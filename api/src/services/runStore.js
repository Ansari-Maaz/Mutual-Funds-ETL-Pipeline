const { runSources } = require('./etlRunner');

const LOCK_ID = '7123094102';
const active = new Set();
const runningOperations = new Set();

function scheduleRun(pool, runId, sourceIds, runner = launchRun) {
  const operation = Promise.resolve().then(() => runner(pool, runId, sourceIds));
  runningOperations.add(operation);
  operation.then(() => runningOperations.delete(operation), () => runningOperations.delete(operation));
  return operation;
}

async function waitForRuns() {
  await Promise.allSettled([...runningOperations]);
}

async function recoverStaleRuns(pool) {
  const client = await pool.connect();
  let locked = false;
  try {
    const lock = await client.query('SELECT pg_try_advisory_lock($1::bigint) AS locked', [LOCK_ID]);
    locked = lock.rows[0].locked;
    if (!locked) return false;
    await client.query("UPDATE api_etl_runs SET status='failed', finished_at=now(), error=COALESCE(error,'API restarted while this run was active') WHERE status IN ('queued','running')");
    return true;
  } finally {
    if (locked) await client.query('SELECT pg_advisory_unlock($1::bigint)', [LOCK_ID]).catch(() => {});
    client.release();
  }
}

async function launchRun(pool, runId, sourceIds) {
  let lockClient;
  try {
    lockClient = await pool.connect();
    const lock = await lockClient.query('SELECT pg_try_advisory_lock($1::bigint) AS locked', [LOCK_ID]);
    if (!lock.rows[0].locked) throw new Error('Another ETL run is already active on this database');
    active.add(runId);
    await pool.query("UPDATE api_etl_runs SET status='running', started_at=now() WHERE id=$1", [runId]);
    const outcome = await runSources(sourceIds);
    const results = outcome.results || safeParse(outcome.stdout);
    const failedCount = results.filter((row) => row.status !== 'Succeeded').length;
    const status = outcome.exitCode === 0 && failedCount === 0 ? 'succeeded' : (results.some((row) => row.status === 'Succeeded') ? 'partially_succeeded' : 'failed');
    const error = outcome.error || (outcome.exitCode !== 0 ? `Python process exited with code ${outcome.exitCode}` : null);
    await pool.query(
      'UPDATE api_etl_runs SET status=$2, finished_at=now(), stdout=$3, stderr=$4, exit_code=$5, results=$6::jsonb, error=$7 WHERE id=$1',
      [runId, status, outcome.stdout || '', outcome.stderr || '', outcome.exitCode, JSON.stringify(results), error],
    );
  } catch (error) {
    await pool.query("UPDATE api_etl_runs SET status='failed', finished_at=now(), error=$2 WHERE id=$1", [runId, error.message]).catch(() => {});
  } finally {
    active.delete(runId);
    if (lockClient) {
      await lockClient.query('SELECT pg_advisory_unlock($1::bigint)', [LOCK_ID]).catch(() => {});
      lockClient.release();
    }
  }
}

function safeParse(stdout = '') {
  const start = stdout.indexOf('['); const end = stdout.lastIndexOf(']');
  if (start < 0 || end < start) return [];
  try { const parsed = JSON.parse(stdout.slice(start, end + 1)); return Array.isArray(parsed) ? parsed : []; } catch { return []; }
}

module.exports = { active, launchRun, scheduleRun, waitForRuns, recoverStaleRuns };
