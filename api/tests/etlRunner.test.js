const { EventEmitter } = require('node:events');
const { execute, parseResults } = require('../src/services/etlRunner');

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
});
