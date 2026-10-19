const { spawn } = require('node:child_process');
const path = require('node:path');
const { projectRoot, pythonExecutable, etlTimeoutMs } = require('../config');
const { runnableSources } = require('./catalog');
const children = new Set();
function sanitize(text) {
  return String(text).replace(/(postgres(?:ql)?:\/\/[^:\s/]+:)[^@\s/]+(@)/gi, '$1[REDACTED]$2')
    .replace(/(password|api[_-]?key|access[_-]?token)(\s*[=:]\s*)[^\s,;]+/gi, '$1$2[REDACTED]');
}

function execute(pythonArgs, { timeoutMs = etlTimeoutMs, spawnProcess = spawn } = {}) {
  return new Promise((resolve) => {
    const child = spawnProcess(pythonExecutable, pythonArgs, { cwd: projectRoot, shell: false, env: { ...process.env, PYTHONUNBUFFERED: '1' } });
    children.add(child);
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const limit = 2_000_000;
    const append = (current, chunk) => (current + chunk.toString()).slice(-limit);
    child.stdout.on('data', (chunk) => { stdout = append(stdout, chunk); });
    child.stderr.on('data', (chunk) => { stderr = append(stderr, chunk); });
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGTERM'); setTimeout(() => child.kill('SIGKILL'), 5000).unref(); }, timeoutMs);
    child.on('error', (error) => { clearTimeout(timer); children.delete(child); resolve({ exitCode: null, stdout: sanitize(stdout), stderr: sanitize(stderr), error: sanitize(error.message), timedOut }); });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      children.delete(child);
      resolve({ exitCode: code, signal, stdout: sanitize(stdout), stderr: sanitize(stderr), timedOut, error: timedOut ? `ETL process exceeded ${timeoutMs}ms timeout` : null });
    });
  });
}

async function terminateChildren() {
  const running = [...children];
  for (const child of running) child.kill('SIGTERM');
  if (running.length) await Promise.race([
    Promise.all(running.map((child) => new Promise((resolve) => child.once('close', resolve)))),
    new Promise((resolve) => setTimeout(resolve, 6000)),
  ]);
}

function parseResults(stdout) {
  const start = stdout.indexOf('[');
  const end = stdout.lastIndexOf(']');
  if (start < 0 || end < start) return [];
  try { const parsed = JSON.parse(stdout.slice(start, end + 1)); return Array.isArray(parsed) ? parsed : []; }
  catch { return []; }
}

async function runSources(sourceIds) {
  const isFullRun = sourceIds.length === runnableSources.size
    && sourceIds.every((sourceId) => runnableSources.has(sourceId));
  const args = isFullRun
    ? ['-m', 'app.cli', 'run', '--all']
    : null;
  if (args) return execute(args);
  let stdout = '';
  let stderr = '';
  const results = [];
  for (const sourceId of sourceIds) {
    const result = await execute(['-m', 'app.cli', 'run', '--source', sourceId]);
    stdout = (stdout + result.stdout).slice(-2_000_000);
    stderr = (stderr + result.stderr).slice(-2_000_000);
    const parsed = parseResults(result.stdout);
    if (parsed.length) results.push(...parsed);
    else results.push({ source_id: sourceId, status: result.exitCode === 0 ? 'Failed' : 'Failed', error: result.error || 'Python ETL did not return structured results' });
    if (result.exitCode !== 0) break;
  }
  return { exitCode: results.every((row) => row.status === 'Succeeded') ? 0 : 1, stdout, stderr, results };
}

module.exports = { execute, parseResults, runSources, terminateChildren, sanitize };
