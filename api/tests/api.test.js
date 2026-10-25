const request = require('supertest');
const { createApp } = require('../src/app');
const { active } = require('../src/services/runStore');

const funds = [{ id: 7, source_id: 'cvm_open_fund_data', source_fund_id: 'F-1', name: 'Example Fund', domicile_country: 'BR', currency: 'BRL', isin: null }];
function fakePool(query = vi.fn()) { return { query }; }

describe('REST API contract', () => {
  beforeEach(() => { active.clear(); process.env.ADMIN_API_KEY = 'test-admin-key'; });

  test('health endpoint returns version and healthy status', async () => {
    const app = createApp({ pool: fakePool() });
    const res = await request(app).get('/health').expect(200);
    expect(res.body).toMatchObject({ status: 'ok', version: '1.0.0' });
  });

  test('database health reports successful connectivity', async () => {
    const pool = fakePool(vi.fn().mockResolvedValue({ rows: [{ '?column?': 1 }] }));
    await request(createApp({ pool })).get('/api/v1/health/database').expect(200, { status: 'ok', database: 'connected' });
  });

  test('database health returns 503 on connection failure', async () => {
    const pool = fakePool(vi.fn().mockRejectedValue(new Error('connection refused')));
    const res = await request(createApp({ pool })).get('/api/v1/health/database').expect(503);
    expect(res.body.error.code).toBe('DATABASE_UNAVAILABLE');
  });

  test('country and registered source endpoints return configured records', async () => {
    const pool = fakePool(vi.fn().mockResolvedValue({ rows: [{ code: 'BR', source_count: 1, fund_count: 1, ingested_source_count: 1, nav_count: 3 }] }));
    const app = createApp({ pool });
    const countries = await request(app).get('/api/v1/countries').expect(200);
    expect(countries.body.data[0]).toMatchObject({ code: 'BR', fund_count: 1 });
    pool.query.mockResolvedValueOnce({ rows: [{ source_id: 'cvm_open_fund_data', country_code: 'BR', organization: 'CVM' }] });
    const sources = await request(app).get('/api/v1/sources').expect(200);
    expect(sources.body.data[0].source_id).toBe('cvm_open_fund_data');
  });

  test('fund pagination/filtering are parameterized and return database rows', async () => {
    const query = vi.fn().mockResolvedValueOnce({ rows: [{ total: 1 }] }).mockResolvedValueOnce({ rows: funds });
    const res = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds?page=2&limit=10&country=BR&q=%27%20OR%201%3D1').expect(200);
    expect(res.body.pagination).toMatchObject({ page: 2, limit: 10, total: 1 });
    expect(res.body.data[0].name).toBe('Example Fund');
    expect(query.mock.calls[0][0]).not.toContain("' OR 1=1");
    expect(query.mock.calls[0][1][1]).toBe("%' OR 1=1%");
  });

  test('rejects invalid pagination and invalid fund ids', async () => {
    const app = createApp({ pool: fakePool() });
    await request(app).get('/api/v1/funds?limit=1000').expect(400);
    await request(app).get('/api/v1/funds/not-an-id').expect(400);
  });

  test('fund details return a real record and a missing id is 404', async () => {
    const query = vi.fn().mockResolvedValueOnce({ rows: funds }).mockResolvedValueOnce({ rows: [] });
    const app = createApp({ pool: fakePool(query) });
    const found = await request(app).get('/api/v1/funds/7').expect(200);
    expect(found.body.data.name).toBe('Example Fund');
    await request(app).get('/api/v1/funds/999').expect(404);
  });

  test('fund details include source metadata and the latest NAV when available', async () => {
    const query = vi.fn().mockResolvedValue({
      rows: [{
        ...funds[0],
        provider: 'Official Asset Manager',
        category: 'Equity',
        source_organization: 'CVM',
        source_name: 'Official fund data',
        source_endpoint_url: 'https://dados.cvm.gov.br/',
        latest_nav: '12.3400000000',
        latest_nav_date: '2026-10-19',
        latest_nav_currency: 'BRL',
      }],
    });
    const res = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds/7').expect(200);
    expect(res.body.data).toMatchObject({
      provider: 'Official Asset Manager',
      category: 'Equity',
      latestNav: { value: '12.3400000000', date: '2026-10-19', currency: 'BRL' },
      source: { organization: 'CVM', url: 'https://dados.cvm.gov.br/' },
    });
  });

  test('source checks reject a URL that is outside the documented official host', async () => {
    const query = vi.fn().mockResolvedValue({ rows: [{ source_id: 'cvm_open_fund_data', endpoint_url: 'https://example.org/steal' }] });
    const res = await request(createApp({ pool: fakePool(query) })).post('/api/v1/sources/cvm_open_fund_data/check').expect(422);
    expect(res.body.error.code).toBe('SOURCE_URL_NOT_ALLOWLISTED');
  });

  test('source connectivity timeout is saved and returned as an unavailable check', async () => {
    const oldFetch = global.fetch;
    global.fetch = vi.fn().mockRejectedValue(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    const query = vi.fn().mockResolvedValueOnce({ rows: [{ source_id: 'cvm_open_fund_data', endpoint_url: 'https://dados.cvm.gov.br/dataset/fi-doc-inf_diario' }] }).mockResolvedValueOnce({ rows: [] });
    try {
      const res = await request(createApp({ pool: fakePool(query) })).post('/api/v1/sources/cvm_open_fund_data/check').expect(502);
      expect(res.body.data.status).toBe('unavailable');
      expect(res.body.data.message).toMatch(/timed out/);
      expect(query).toHaveBeenCalledTimes(2);
    } finally { global.fetch = oldFetch; }
  });

  test('ETL start requires admin authentication', async () => {
    const res = await request(createApp({ pool: fakePool() })).post('/api/v1/etl/runs').send({ all: true }).expect(401);
    expect(res.body.error.code).toBe('UNAUTHORIZED');
  });

  test('ETL start validates sources and accepts an authenticated request', async () => {
    const query = vi.fn().mockResolvedValue({ rows: [] });
    const launch = vi.fn();
    const res = await request(createApp({ pool: fakePool(query), etlLauncher: launch })).post('/api/v1/etl/runs').set('X-API-Key', 'test-admin-key').send({ sourceIds: ['bogus'] }).expect(400);
    expect(res.body.error.code).toBe('UNKNOWN_SOURCE');
    const accepted = await request(createApp({ pool: fakePool(query), etlLauncher: launch })).post('/api/v1/etl/runs').set('X-API-Key', 'test-admin-key').send({ sourceIds: ['cvm_open_fund_data'] }).expect(202);
    expect(accepted.body.data.status).toBe('queued');
    await new Promise((resolve) => setImmediate(resolve));
    expect(launch).toHaveBeenCalledTimes(1);
  });

  test('a concurrent local ETL start is rejected', async () => {
    active.add('running-test');
    const res = await request(createApp({ pool: fakePool() })).post('/api/v1/etl/runs').set('X-API-Key', 'test-admin-key').send({ all: true }).expect(409);
    expect(res.body.error.code).toBe('ETL_ALREADY_RUNNING');
  });

  test('run-history rejects malformed IDs rather than passing them to PostgreSQL', async () => {
    const query = vi.fn();
    await request(createApp({ pool: fakePool(query) })).get('/api/v1/etl/runs/not-a-uuid').expect(400);
    expect(query).not.toHaveBeenCalled();
  });
});
