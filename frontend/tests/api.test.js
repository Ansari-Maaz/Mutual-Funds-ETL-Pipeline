import test from 'node:test';
import assert from 'node:assert/strict';
import { request, resolveApiBase } from '../src/api.js';

test('API base prefers configured host and removes trailing slashes', () => {
  assert.equal(resolveApiBase('https://api.example.test///', 'http://localhost:5173'), 'https://api.example.test');
  assert.equal(resolveApiBase('', 'http://localhost:5173/'), 'http://localhost:5173');
});

test('request sends JSON headers, preserves caller headers, and parses JSON', async () => {
  const originalFetch = globalThis.fetch;
  let observed;
  globalThis.fetch = async (url, options) => {
    observed = { url, options };
    return { ok: true, status: 200, json: async () => ({ data: [{ id: 12 }] }) };
  };

  try {
    const result = await request('/api/v1/funds', { headers: { 'X-API-Key': 'test-key' } });
    assert.equal(observed.url, 'http://localhost/api/v1/funds');
    assert.equal(observed.options.headers['Content-Type'], 'application/json');
    assert.equal(observed.options.headers['X-API-Key'], 'test-key');
    assert.deepEqual(result.body, { data: [{ id: 12 }] });
    assert.equal(result.response.status, 200);
    assert.equal(Number.isFinite(result.elapsed), true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('request returns a null body for non-JSON error responses', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => { throw new SyntaxError('bad JSON'); } });
  try {
    const result = await request('/api/v1/stats');
    assert.equal(result.response.status, 503);
    assert.equal(result.body, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
