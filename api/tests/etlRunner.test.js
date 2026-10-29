const { EventEmitter } = require('node:events');
const { execute, parseResults, runSources } = require('../src/services/etlRunner');

function childProcess() {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.kill = vi.fn((signal) => { setImmediate(() => child.emit('close', null, signal)); return true; });
  return child;
}

describe('Python ETL process integration', () => {
  afterEach(() => vi.clearAllMocks());

  test('captures output and a nonzero process exit code', async () => {
    const child = childProcess(); const spawnProcess = vi.fn(() => child);
    setImmediate(() => { child.stdout.emit('data', Buffer.from('[{"source_id":"cvm_open_fund_data","status":"Failed"}]')); child.stderr.emit('data', Buffer.from('provider unavailable')); child.emit('close', 2, null); });
    const result = await execute(['-m','app.cli','run','--source','cvm_open_fund_data'], { spawnProcess });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('provider unavailable');
    expect(parseResults(result.stdout)[0].status).toBe('Failed');
  });

  test('terminates and reports a timed out ETL process', async () => {
    const child = childProcess(); const spawnProcess = vi.fn(() => child);
    const result = await execute(['-m','app.cli','run','--all'], { timeoutMs: 5, spawnProcess });
    expect(child.kill).toHaveBeenCalledWith('SIGTERM');
    expect(result.timedOut).toBe(true);
    expect(result.error).toMatch(/timeout/);
  });

  test('selected sources run in one CLI process so a failure cannot hide later outcomes', async () => {
    const run = vi.fn().mockResolvedValue({ exitCode: 1, stdout: '[{"source_id":"cvm_open_fund_data","status":"Failed"},{"source_id":"gsfm_unit_prices","status":"Succeeded"}]', stderr: '' });
    const result = await runSources(['cvm_open_fund_data', 'gsfm_unit_prices'], run);
    expect(result.results).toHaveLength(2);
    expect(run).toHaveBeenCalledTimes(1);
    expect(run.mock.calls[0][0]).toContain('cvm_open_fund_data');
    expect(run.mock.calls[0][0]).toContain('gsfm_unit_prices');
  });
});
