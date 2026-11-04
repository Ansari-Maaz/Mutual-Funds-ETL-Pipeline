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

  test('hosted API reference serves an interactive page and its OpenAPI contract', async () => {
    const app = createApp({ pool: fakePool() });
    const page = await request(app).get('/api/docs').expect(200);
    expect(page.text).toContain('<title>FundFlow API Reference</title>');
    expect(page.text).toContain('spec-url="/api/openapi.json"');
    expect(page.headers['content-security-policy']).toContain('https://cdn.jsdelivr.net');

    const spec = await request(app).get('/api/openapi.json').expect(200);
    expect(spec.body.openapi).toBe('3.0.3');
    expect(spec.body.paths['/funds/{fund_id}/holdings'].get.operationId).toBe('getFundHoldings');
    expect(spec.body.paths['/etl/runs'].post.security).toEqual([{ AdminApiKey: [] }]);
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
    expect(countries.body.data[0]).toMatchObject({ code: 'BRA', iso2Code: 'BR', fund_count: 1 });
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
        latest_nav_source_id: 'cvm_open_fund_data',
        latest_nav_source_url: 'https://dados.cvm.gov.br/data.csv',
      }],
    });
    const res = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds/7').expect(200);
    expect(res.body.data).toMatchObject({
      provider: 'Official Asset Manager',
      category: 'Equity',
      latestNav: { value: '12.3400000000', date: '2026-10-19', currency: 'BRL', sourceId: 'cvm_open_fund_data', sourceUrl: 'https://dados.cvm.gov.br/data.csv' },
      source: { organization: 'CVM', url: 'https://dados.cvm.gov.br/' },
    });
  });

  test('NAV history returns per-observation source provenance when known', async () => {
    const query = vi.fn().mockResolvedValue({ rows: [{ id: 12, fund_id: 7, valuation_date: '2026-10-19', nav: '12.34', currency: 'BRL', source_id: 'cvm_open_fund_data', source_url: 'https://dados.cvm.gov.br/data.csv', retrieved_at: '2026-10-20T00:00:00Z' }] });
    const response = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds/7/nav?limit=1').expect(200);
    expect(response.body.data[0]).toMatchObject({ source_id: 'cvm_open_fund_data', source_url: 'https://dados.cvm.gov.br/data.csv' });
    expect(query.mock.calls[0][0]).toContain('source_id,source_url');
  });

  test('fund profile data returns source-backed dated provider snapshots', async () => {
    const query = vi.fn()
      .mockResolvedValueOnce({ rows: [{ id: 7 }] })
      .mockResolvedValueOnce({ rows: [{
        id: 51, dataset: 'performance', source_id: 'us_vanguard_fund_products',
        source_report_date: '2026-10-31', payload: { metric: 'oneYearReturn', value: 12.05, unit: 'percent' },
        source_url: 'https://advisors.vanguard.com/investments/products/vfiax/',
        retrieved_at: '2026-11-04T10:00:00Z', source_organization: 'The Vanguard Group',
        source_name: 'Vanguard official fund product pages',
      }] })
      .mockResolvedValueOnce({ rows: [{ dataset: 'performance' }] });
    const response = await request(createApp({ pool: fakePool(query) }))
      .get('/api/v1/funds/7/profile-data?dataset=performance').expect(200);
    expect(response.body).toMatchObject({
      status: 'available', datasets: ['performance'], count: 1,
      data: [{ dataset: 'performance', source_id: 'us_vanguard_fund_products',
        source_report_date: '2026-10-31', payload: { metric: 'oneYearReturn', value: 12.05 },
        source_organization: 'The Vanguard Group' }],
    });
  });

  test('fund holdings return filed positions and sourced optional metrics by reporting date', async () => {
    const query = vi.fn()
      .mockResolvedValueOnce({ rows: [{ holdings_status: 'available', holdings_report_date: '2026-06-30' }] })
      .mockResolvedValueOnce({ rows: [{ reporting_date: '2026-06-30' }, { reporting_date: '2026-03-31' }] })
      .mockResolvedValueOnce({ rows: [{
        id: 42, fund_id: 7, reporting_date: '2026-06-30', security_name: 'Example issuer',
        ticker: 'EXM', isin: 'US0000000001', quantity: '10', market_value: '250', currency: 'USD',
        portfolio_weight: '2.5', first_bought_date: null, share_change_percentage: null,
        one_year_return: null, forward_pe: null, sector: null, data_source: 'sec_edgar_nport',
        source_url: 'https://www.sec.gov/Archives/example.xml', metrics_source: null,
        data_scope: 'SEC series-level; shared across share classes', sec_series_id: 'S000000001',
      }] });
    const res = await request(createApp({ pool: fakePool(query) }))
      .get('/api/v1/funds/7/holdings?report_date=2026-06-30').expect(200);
    expect(res.body).toMatchObject({
      status: 'available', reportDate: '2026-06-30', reportDates: ['2026-06-30', '2026-03-31'],
      data: [{ security_name: 'Example issuer', ticker: 'EXM', isin: 'US0000000001',
        portfolio_weight: '2.5', data_source: 'sec_edgar_nport',
        source_url: 'https://www.sec.gov/Archives/example.xml',
        data_scope: 'SEC series-level; shared across share classes', sec_series_id: 'S000000001' }],
    });
    expect(query.mock.calls[2][0]).toContain('FROM portfolio_holdings h');
    expect(query.mock.calls[2][0]).toContain('FROM holding_metrics');
    expect(query.mock.calls[2][1]).toEqual([7, '2026-06-30', 1000]);
  });

  test('fund completeness keeps missing data unverified and marks US AMFI as not applicable', async () => {
    const query = vi.fn()
      .mockResolvedValueOnce({ rows: [{ id: 7, domicile_country: 'US', name: 'Example Fund', ticker: 'EXM', isin: null, currency: 'USD', provider: 'Example', category: null, fund_type: 'Open-end mutual fund', inception_date: null, status: 'Registered', official_url: 'https://sec.gov/', manager: null, sec_cik: '0000000001', sec_series_id: 'S000000001', holdings_status: 'not_checked' }] })
      .mockResolvedValueOnce({ rows: [{ count: 2, first_date: '2026-10-01', latest_date: '2026-10-02' }] })
      .mockResolvedValueOnce({ rows: [{ count: 0, first_date: null, latest_date: null }] })
      .mockResolvedValueOnce({ rows: [{ dataset: 'nav_history', count: 2, report_dates: 2, scopes: 1, first_date: '2026-08-31', latest_date: '2026-09-30' }] })
      .mockResolvedValueOnce({ rows: [{ payload: { cusip: '123456789', benchmark: 'Example Index', objective: 'Tracks an example index.' } }] });
    const response = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds/7/completeness').expect(200);
    expect(response.body.data.status).toBe('incomplete');
    expect(response.body.data.datasets.find((item) => item.dataset === 'daily_nav_history')).toMatchObject({ status: 'partially_available', records: 2 });
    expect(response.body.data.datasets.find((item) => item.dataset === 'money_market_nav_history')).toMatchObject({
      status: 'partially_available', records: 2,
      note: expect.stringContaining('currency is not provided'),
    });
    expect(response.body.data.datasets.find((item) => item.dataset === 'amfi_code').status).toBe('not_applicable');
    expect(response.body.data.datasets.find((item) => item.dataset === 'aum_history').status).toBe('requires_verification');
    expect(response.body.data.fields.find((item) => item.field === 'cusip')).toMatchObject({ status: 'available', value: '123456789' });
    expect(response.body.data.fields.find((item) => item.field === 'fund_manager').status).toBe('requires_verification');
    expect(response.body.data.fields.find((item) => item.field === 'share_class').status).toBe('requires_verification');
    expect(response.body.data.fields.find((item) => item.field === 'distribution_option').status).toBe('requires_verification');
  });

  test('fund completeness does not call mixed-scope AUM snapshots a complete history', async () => {
    const query = vi.fn()
      .mockResolvedValueOnce({ rows: [{ id: 7, domicile_country: 'US', name: 'Example Fund', ticker: 'EXM', currency: 'USD', provider: 'Example', holdings_status: 'not_checked' }] })
      .mockResolvedValueOnce({ rows: [{ count: 0, first_date: null, latest_date: null }] })
      .mockResolvedValueOnce({ rows: [{ count: 0, first_date: null, latest_date: null }] })
      .mockResolvedValueOnce({ rows: [{ dataset: 'aum_history', count: 3, report_dates: 2, scopes: 2, first_date: '2026-06-30', latest_date: '2026-10-31' }] })
      .mockResolvedValueOnce({ rows: [] });
    const response = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds/7/completeness').expect(200);
    expect(response.body.data.datasets.find((item) => item.dataset === 'aum_history')).toMatchObject({
      status: 'partially_available', records: 3, firstReportDate: '2026-06-30', latestReportDate: '2026-10-31',
    });
  });

  test('fund completeness keeps source snapshots partial without history completeness evidence', async () => {
    const query = vi.fn()
      .mockResolvedValueOnce({ rows: [{ ...funds[0], domicile_country: 'US', holdings_status: 'not_checked' }] })
      .mockResolvedValueOnce({ rows: [{ count: 0, first_date: null, latest_date: null }] })
      .mockResolvedValueOnce({ rows: [{ count: 0, first_date: null, latest_date: null }] })
      .mockResolvedValueOnce({ rows: [{ dataset: 'performance', count: 2, report_dates: 2, scopes: 1, first_date: '2025-10-31', latest_date: '2026-10-31' }] })
      .mockResolvedValueOnce({ rows: [] });
    const response = await request(createApp({ pool: fakePool(query) })).get('/api/v1/funds/7/completeness').expect(200);
    expect(response.body.data.datasets.find((item) => item.dataset === 'performance')).toMatchObject({
      status: 'partially_available', records: 2,
    });
  });

  test('source checks reject a URL that is outside the documented official host', async () => {
    const query = vi.fn().mockResolvedValue({ rows: [{ source_id: 'cvm_open_fund_data', endpoint_url: 'https://example.org/steal' }] });
    const res = await request(createApp({ pool: fakePool(query) })).post('/api/v1/sources/cvm_open_fund_data/check').set('X-API-Key', 'test-admin-key').expect(422);
    expect(res.body.error.code).toBe('SOURCE_URL_NOT_ALLOWLISTED');
  });

  test('source check without an endpoint returns 422 instead of an unhandled URL error', async () => {
    const query = vi.fn().mockResolvedValue({ rows: [{ source_id: 'au_user_managed_funds', endpoint_url: null }] });
    const res = await request(createApp({ pool: fakePool(query) }))
      .post('/api/v1/sources/au_user_managed_funds/check').set('X-API-Key', 'test-admin-key').expect(422);
    expect(res.body.error.code).toBe('SOURCE_ENDPOINT_MISSING');
    expect(query).toHaveBeenCalledTimes(1);
  });

  test('source connectivity timeout is saved and returned as an unavailable check', async () => {
    const oldFetch = global.fetch;
    global.fetch = vi.fn().mockRejectedValue(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    const query = vi.fn().mockResolvedValueOnce({ rows: [{ source_id: 'cvm_open_fund_data', endpoint_url: 'https://dados.cvm.gov.br/dataset/fi-doc-inf_diario' }] }).mockResolvedValueOnce({ rows: [] });
    try {
      const res = await request(createApp({ pool: fakePool(query) })).post('/api/v1/sources/cvm_open_fund_data/check').set('X-API-Key', 'test-admin-key').expect(502);
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

  test('a database-wide active-run conflict returns 409 without queueing a second job', async () => {
    const conflict = Object.assign(new Error('duplicate active run'), {
      code: '23505', constraint: 'uq_api_etl_runs_single_active',
    });
    const query = vi.fn().mockRejectedValue(conflict);
    const res = await request(createApp({ pool: fakePool(query) }))
      .post('/api/v1/etl/runs').set('X-API-Key', 'test-admin-key')
      .send({ sourceIds: ['cvm_open_fund_data'] }).expect(409);
    expect(res.body.error.code).toBe('ETL_ALREADY_RUNNING');
  });

  test('run-history rejects malformed IDs rather than passing them to PostgreSQL', async () => {
    const query = vi.fn();
    await request(createApp({ pool: fakePool(query) })).get('/api/v1/etl/runs/not-a-uuid').expect(400);
    expect(query).not.toHaveBeenCalled();
  });
});
