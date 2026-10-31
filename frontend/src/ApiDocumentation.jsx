import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Check, Code2, Copy, ExternalLink, Menu, Moon, Play, Search, Shield, Sun, X } from 'lucide-react';
import { apiBase } from './api';
import './api-docs.css';

const groups = [
  { title: 'Getting started', items: [
    { id: 'intro', title: 'Introduction', kind: 'guide' },
    { id: 'quickstart', title: 'Quickstart', kind: 'guide' },
    { id: 'errors', title: 'Errors', kind: 'guide' },
  ] },
  { title: 'Health & status', items: [
    { id: 'health', title: 'API health', method: 'GET', path: '/health' },
    { id: 'db-health', title: 'Database health', method: 'GET', path: '/api/v1/health/database' },
    { id: 'etl-health', title: 'Latest ETL status', method: 'GET', path: '/api/v1/health/etl' },
  ] },
  { title: 'Catalog', items: [
    { id: 'stats', title: 'Database statistics', method: 'GET', path: '/api/v1/stats' },
    { id: 'countries', title: 'Countries', method: 'GET', path: '/api/v1/countries' },
    { id: 'sources', title: 'Sources', method: 'GET', path: '/api/v1/sources' },
    { id: 'source-detail', title: 'Source detail', method: 'GET', path: '/api/v1/sources/{source_id}', params: [['source_id','string','required','Source registry ID']] },
    { id: 'source-check', title: 'Check a source', method: 'POST', path: '/api/v1/sources/{source_id}/check', auth: true, params: [['source_id','string','required','Source registry ID']] },
  ] },
  { title: 'Fund data', items: [
    { id: 'funds', title: 'Search funds', method: 'GET', path: '/api/v1/funds', params: [['page','integer','optional','Page number (default 1)'],['limit','integer','optional','Page size (1–100, default 25)'],['q','string','optional','Search fund name or identifier'],['country','string','optional','Two-letter country code'],['currency','string','optional','Three-letter currency code'],['isin','string','optional','ISIN filter'],['category','string','optional','Fund category'],['fund_type','string','optional','Fund type'],['status','string','optional','Fund status'],['has_nav','boolean','optional','Filter funds with or without NAV'],['holdings_status','string','optional','available, unavailable, or not_checked'],['sort','string','optional','name, country, currency, retrieved_at'],['order','string','optional','asc or desc']] },
    { id: 'fund', title: 'Fund profile', method: 'GET', path: '/api/v1/funds/{fund_id}', params: [['fund_id','integer','required','Database fund ID']] },
    { id: 'nav', title: 'NAV history', method: 'GET', path: '/api/v1/funds/{fund_id}/nav', params: [['fund_id','integer','required','Database fund ID'],['from','date','optional','First valuation date (inclusive)'],['to','date','optional','Last valuation date (inclusive)'],['limit','integer','optional','Maximum 5,000 rows (default 1,000)']] },
    { id: 'holdings', title: 'Portfolio holdings', method: 'GET', path: '/api/v1/funds/{fund_id}/holdings', params: [['fund_id','integer','required','Database fund ID'],['report_date','date','optional','Return one reporting period'],['limit','integer','optional','Maximum 5,000 rows (default 1,000)']] },
  ] },
  { title: 'ETL operations', items: [
    { id: 'runs', title: 'ETL run history', method: 'GET', path: '/api/v1/etl/runs', params: [['limit','integer','optional','Maximum 100 runs (default 20)']] },
    { id: 'run-detail', title: 'ETL run detail', method: 'GET', path: '/api/v1/etl/runs/{id}', params: [['id','string','required','Run ID']] },
    { id: 'start-run', title: 'Start ETL run', method: 'POST', path: '/api/v1/etl/runs', auth: true, body: '{\n  "all": true\n}' },
  ] },
];
const allItems = groups.flatMap((g) => g.items);
const examples = {
  intro: `# FundFlow API\n\nFundFlow provides read access to mutual fund catalog records, NAV history, portfolio holdings, source coverage, and ETL run status stored in the configured database.\n\nPublic read endpoints do not require an account or API key. Administrative operations require the server's configured API key.\n\nData availability and freshness depend on each source and the latest successful ingestion. Missing fields remain null; FundFlow does not infer unavailable source data.`,
  quickstart: `curl '${apiBase}/api/v1/funds?country=US&limit=10'`,
  errors: `HTTP 400  Invalid query or identifier\nHTTP 401  Missing or invalid administrator API key\nHTTP 404  Fund or source was not found\nHTTP 409  An ETL run is already active\nHTTP 422  Source has no valid endpoint configured\nHTTP 500  Unexpected API or database error\nHTTP 503  Database is unavailable`,
  health: `{"status":"ok","version":"<api version>","timestamp":"<timestamp>"}`,
  'db-health': `{"status":"ok","database":"connected"}`,
  'etl-health': `{"status":"ok","latestRun":{"id":"<run ID>","status":"<run status>","requested_at":"<timestamp>","started_at":"<timestamp>","finished_at":"<timestamp or null>"}}`,
  stats: `{"data":{"totalFunds":"<integer from database>","navObservations":"<integer from database>","configuredCountries":"<integer from database>","registeredSources":"<integer from database>"}}`,
  countries: `{"data":[{"code":"<country code>","name":"<country name>","fund_count":"<integer from database>","nav_count":"<integer from database>"}]}`,
  sources: `{"data":[{"source_id":"<source ID>","country_code":"<country code>","organization":"<source organization>","integration_status":"<status>","fund_count":"<integer from database>"}]}`,
  funds: `{"data":[{"id":"<fund ID>","name":"<fund name>","country":"<country code>","currency":"<currency>","isin":null,"holdingsStatus":"<status>"}],"pagination":{"page":"<page>","limit":"<page size>","total":"<database total>","pages":"<page count>"}}`,
  fund: `{"data":{"id":"<fund ID>","name":"<fund name>","country":"<country code>","currency":"<currency>","latestNav":null}}`,
  nav: `{"data":[{"id":"<observation ID>","fund_id":"<fund ID>","valuation_date":"<date>","nav":"<source value>","currency":"<currency>"}],"count":"<row count>"}`,
  holdings: `{"data":[{"fund_id":"<fund ID>","reporting_date":"<official reporting date>","security_name":"<reported security name>","ticker":null,"quantity":null,"market_value":null,"portfolio_weight":null,"sector":null,"data_source":"<filing source>"}],"status":"<availability status>","reportDate":"<report date or null>","reportDates":["<available reporting dates>"],"count":"<row count>"}`,
  runs: `{"data":[{"id":"<run ID>","status":"<run status>","requested_at":"<timestamp>","finished_at":null,"source_ids":["<source ID>"]}]}`,
  'run-detail': `{"data":{"id":"<run ID>","status":"<run status>","source_ids":["<source ID>"],"requested_at":"<timestamp>","finished_at":null,"results":[]}}`,
  'source-check': `{"data":{"sourceId":"<source ID>","status":"<reachable | rate_limited | unavailable>","httpStatus":"<http status or null>","responseTimeMs":"<milliseconds>","message":null,"note":"Connectivity only; this does not validate source data or confirm an ETL load."}}`,
  'start-run': `{"data":{"id":"<run ID>","status":"queued","sourceIds":["<configured source ID>"],"requestedAt":"<timestamp>"}}`,
};
const human = (id) => allItems.find((i) => i.id === id);

export default function ApiDocumentation() {
  const [theme, setTheme] = useState(() => localStorage.getItem('fundflow-theme') || document.documentElement.dataset.theme || 'light');
  const [activeId, setActiveId] = useState('intro');
  const [search, setSearch] = useState('');
  const [mobileNav, setMobileNav] = useState(false);
  const [tryOpen, setTryOpen] = useState(false);
  const [response, setResponse] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [fundId, setFundId] = useState('1');
  const [sourceId, setSourceId] = useState('sec_open_end_fund_classes');
  const [query, setQuery] = useState('');
  const [runId, setRunId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [body, setBody] = useState('{\n  "all": true\n}');
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('fundflow-theme', theme); }, [theme]);
  const active = human(activeId) || allItems[0];
  const visibleGroups = useMemo(() => groups.map((g) => ({ ...g, items: g.items.filter((i) => `${i.title} ${i.path || ''} ${g.title}`.toLowerCase().includes(search.toLowerCase())) })).filter((g) => g.items.length), [search]);
  const activePath = (active?.path || '').replace('{fund_id}', encodeURIComponent(fundId)).replace('{id}', encodeURIComponent(activeId === 'run-detail' ? runId || 'python-1' : fundId)).replace('{run_id}', encodeURIComponent(runId || 'python-1')).replace('{source_id}', encodeURIComponent(sourceId));
  const hasBody = active?.id === 'start-run';
  const hasQueryParams = active?.method === 'GET' && active.params?.some(([name]) => !active.path?.includes(`{${name}}`));
  const requestQuery = hasQueryParams ? query.trim().replace(/^\?/, '') : '';
  const curlExample = hasBody
    ? `curl -X POST '${apiBase}${activePath}' \\\n  -H 'Content-Type: application/json' \\\n  -H 'X-API-Key: <admin-key>' \\\n  -d '${body.replaceAll("'", "'\\''")}'`
    : `curl -X ${active.method} '${apiBase}${activePath}${requestQuery ? `?${requestQuery}` : ''}'${active.auth ? " \\\n  -H 'X-API-Key: <admin-key>'" : ''}`;
  const jsExample = hasBody
    ? `const response = await fetch('${apiBase}${activePath}', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json', 'X-API-Key': '<admin-key>' },\n  body: JSON.stringify(${body})\n});\nconst result = await response.json();`
    : `const response = await fetch('${apiBase}${activePath}${requestQuery ? `?${requestQuery}` : ''}', { method: '${active.method}'${active.auth ? ", headers: { 'X-API-Key': '<admin-key>' }" : ''} });\nconst result = await response.json();\nconsole.log(result);`;
  const example = examples[activeId] || `curl '${apiBase}${activePath}'`;
  const selectItem = (id) => { setActiveId(id); setResponse(null); setQuery(''); setRunId(''); setTryOpen(false); setMobileNav(false); };
  const run = async () => {
    setBusy(true); setResponse(null);
    try {
      const suffix = endpointContent && requestQuery ? `${activePath.includes('?') ? '&' : '?'}${requestQuery}` : '';
      const url = `${apiBase}${activePath}${suffix}`;
      const headers = { Accept: 'application/json' };
      if (active?.auth && apiKey) headers['X-API-Key'] = apiKey;
      if (hasBody) headers['Content-Type'] = 'application/json';
      const result = await fetch(url, { method: active.method || 'GET', headers, ...(hasBody ? { body } : {}) });
      const text = await result.text();
      let formatted; try { formatted = JSON.stringify(JSON.parse(text), null, 2); } catch { formatted = text; }
      setResponse({ status: result.status, text: formatted, url });
    } catch (error) { setResponse({ status: 'Network error', text: error.message }); }
    finally { setBusy(false); }
  };
  const copy = async (value) => { try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch {} };
  const openTry = () => { setTryOpen(true); setResponse(null); };
  const endpointContent = active.kind !== 'guide';
  return <div className="docs-shell">
    <header className="docs-topbar"><a href="/" className="docs-brand"><span className="docs-mark">F</span><span>Fund<span>Flow</span><small>API DOCUMENTATION</small></span></a><button className="docs-mobile-toggle" onClick={() => setMobileNav(!mobileNav)} aria-label="Toggle documentation navigation">{mobileNav ? <X size={18}/> : <Menu size={18}/>}</button><div className="docs-top-links"><span>API reference</span><a href={`${apiBase}/api/openapi.json`} target="_blank" rel="noreferrer">OpenAPI spec <ExternalLink size={13}/></a><button className="docs-theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>{theme === 'dark' ? <Sun size={15}/> : <Moon size={15}/>}</button><a href="/">Back to dashboard <ArrowLeft size={13}/></a></div></header>
    <div className="docs-layout">
      <aside className={`docs-sidebar ${mobileNav ? 'open' : ''}`}><a className="docs-back" href="/"><ArrowLeft size={14}/> FundFlow dashboard</a><label className="docs-search"><Search size={15}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search documentation"/></label><div className="docs-nav">{visibleGroups.map((group) => <section key={group.title}><h3>{group.title}</h3>{group.items.map((item) => <button key={item.id} onClick={() => selectItem(item.id)} className={activeId === item.id ? 'selected' : ''}>{item.method && <i className={`method-mini ${item.method.toLowerCase()}`}>{item.method}</i>}<span>{item.title}</span></button>)}</section>)}</div><div className="docs-sidebar-bottom"><Shield size={14}/> Public read API · No account required</div></aside>
      <main className="docs-main"><div className="docs-breadcrumb">Documentation <span>/</span> {groups.find((g) => g.items.some((i) => i.id === activeId))?.title || 'Reference'} <span>/</span> <b>{active.title}</b></div>
        {activeId === 'intro' ? <><div className="docs-title"><div className="docs-eyebrow">FUND FLOW · REST API</div><h1>Build with FundFlow</h1><p>Read database-backed fund, NAV, holdings, source and ETL data through a consistent JSON API.</p></div><section className="docs-card intro-card"><h2><BookOpen size={18}/> API overview</h2><p>FundFlow exposes data collected by its configured connectors and stored in PostgreSQL. Read endpoints are public and do not require signup. Each response reflects the records currently available in the deployment’s database.</p><div className="docs-callout"><b>Data integrity</b><span>Values unavailable from a verified source are returned as <code>null</code> or omitted. A successful health check confirms connectivity; it does not guarantee that a source has supplied data.</span></div><h2>Base URL</h2><div className="docs-code-line"><code>{apiBase}/api/v1</code><button onClick={() => copy(`${apiBase}/api/v1`)}>{copied ? <Check size={14}/> : <Copy size={14}/>} Copy</button></div><h2>Authentication</h2><p>Public read endpoints need no API key. Administrator actions, such as starting an ETL run or checking a source, require the <code>X-API-Key</code> header configured on the API server. No user login or signup is needed.</p><button className="docs-primary" onClick={() => selectItem('quickstart')}>Make your first request <ArrowRight size={15}/></button></section><div className="docs-next"><button onClick={() => selectItem('quickstart')}>Quickstart <ArrowRight size={14}/></button></div></> : activeId === 'quickstart' || activeId === 'errors' ? <><div className="docs-title"><div className="docs-eyebrow">GUIDE</div><h1>{active.title}</h1><p>{activeId === 'quickstart' ? 'Make your first request and inspect live FundFlow data.' : 'Understand the errors returned by FundFlow endpoints.'}</p></div><section className="docs-card"><h2>{activeId === 'quickstart' ? 'Request fund records' : 'HTTP status codes'}</h2><p>{activeId === 'quickstart' ? 'Use any HTTP client. This example reads up to ten US fund records from the configured database.' : 'Errors use a JSON body with an error code and readable message. Database failures are returned as errors instead of empty data.'}</p><pre className="docs-code"><code>{example}</code><button onClick={() => copy(example)}>{copied ? <Check size={14}/> : <Copy size={14}/>} Copy</button></pre>{activeId === 'quickstart' && <button className="docs-primary" onClick={() => { selectItem('funds'); openTry(); }}>Try this request <Play size={14}/></button>}{activeId === 'errors' && <table className="docs-table"><thead><tr><th>HTTP</th><th>Meaning</th></tr></thead><tbody>{[['400','Invalid query or identifier'],['401','Missing or invalid admin API key'],['404','Fund or source not found'],['409','An ETL run is already active'],['422','No valid source endpoint configured'],['500','Unexpected API or database error'],['503','Database unavailable']].map(([a,b])=><tr key={a}><td><code>{a}</code></td><td>{b}</td></tr>)}</tbody></table>}</section></> : <><div className="docs-title"><div className="docs-eyebrow">{active.method} ENDPOINT</div><div className="docs-endpoint-heading"><h1>{active.title}</h1><button className="docs-try-button" onClick={openTry}><Play size={14}/> Try it</button></div><div className="docs-path"><span className={`http-method ${active.method.toLowerCase()}`}>{active.method}</span><code>{active.path}</code><button onClick={() => copy(`${apiBase}${activePath}`)} aria-label="Copy endpoint URL">{copied ? <Check size={14}/> : <Copy size={14}/>}</button></div><p>{describe(active.id)}</p>{active.auth && <div className="docs-auth-note"><Shield size={14}/> Administrator API key required in <code>X-API-Key</code>. This operation may change system state.</div>}</div><div className="docs-tabs"><a href="#parameters">Parameters</a><a href="#response">Response</a><a href="#example">Code examples</a></div><section id="parameters" className="docs-card"><h2>Parameters</h2>{active.params?.length ? <><p>Provide these values in the path or query string.</p><div className="docs-table-wrap"><table className="docs-table"><thead><tr><th>Name</th><th>Type</th><th>In</th><th>Required</th><th>Description</th><th>Example</th></tr></thead><tbody>{active.params.map(([name,type,required,desc])=><tr key={name}><td><code>{name}</code></td><td>{type}</td><td>{active.path.includes(`{${name}}`)?'path':'query'}</td><td><span className={`required-badge ${required}`}>{required}</span></td><td>{desc}</td><td><code>{parameterExample(name)}</code></td></tr>)}</tbody></table></div></> : hasBody ? <p>This endpoint accepts a JSON request body. See the request example below.</p> : <p>This endpoint has no parameters. It reads current data from the configured FundFlow database.</p>}{active.auth && <div className="docs-callout"><b>Authentication</b><span>Include <code>X-API-Key: &lt;admin-key&gt;</code>. Never expose this secret in a public browser app.</span></div>}</section><section id="response" className="docs-card"><div className="docs-section-head"><div><h2>Response</h2><p>Illustrative response shape only. Values in angle brackets are placeholders and are never pulled from or written to your data.</p></div><span className="response-pill">{active.id === 'start-run' ? '202 · application/json' : '200 · application/json'}</span></div><pre className="docs-code"><code>{examples[activeId] || `{"data": []}`}</code></pre></section><section id="example" className="docs-card"><h2><Code2 size={17}/> Code examples</h2><div className="docs-code-label">cURL</div><pre className="docs-code"><code>{curlExample}</code><button onClick={() => copy(curlExample)}>{copied ? <Check size={14}/> : <Copy size={14}/>} Copy</button></pre><div className="docs-code-label">JavaScript</div><pre className="docs-code"><code>{jsExample}</code></pre></section><div className="docs-next"><button onClick={() => selectItem(allItems[(allItems.findIndex((i)=>i.id===activeId)+allItems.length-1)%allItems.length].id)}><ArrowLeft size={14}/> Previous</button><button onClick={() => selectItem(allItems[(allItems.findIndex((i)=>i.id===activeId)+1)%allItems.length].id)}>Next <ArrowRight size={14}/></button></div></>}
      </main>
      <aside className={`docs-try-panel ${tryOpen ? 'visible' : ''}`}><div className="try-head"><div><small>{endpointContent ? 'REQUEST BUILDER' : 'GETTING STARTED'}</small><b>{endpointContent ? 'Try this endpoint' : 'Make your first request'}</b></div><button className="try-close" onClick={() => setTryOpen(false)} aria-label="Close request panel"><X size={16}/></button></div>{endpointContent ? <><label>API HOST<div className="try-host">{apiBase}</div></label><label>METHOD & PATH<div className="try-method"><b className={(active.method || 'GET').toLowerCase()}>{active.method}</b><span>{activePath}</span></div></label>{active.path?.includes('{fund_id}') && <label>FUND ID<input value={fundId} onChange={(e)=>setFundId(e.target.value)} inputMode="numeric" /></label>}{active.path?.includes('{source_id}') && <label>SOURCE ID<input value={sourceId} onChange={(e)=>setSourceId(e.target.value)} /></label>}{(active.path?.includes('{run_id}') || active.id === 'run-detail') && <label>RUN ID<input value={runId} onChange={(e)=>setRunId(e.target.value)} placeholder="python-1 or API UUID" /></label>}{hasQueryParams && <label>QUERY PARAMETERS<textarea value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="limit=25" /></label>}{active.auth && <label>ADMIN API KEY<input type="password" value={apiKey} onChange={(e)=>setApiKey(e.target.value)} placeholder="X-API-Key" autoComplete="off"/><small>Kept in this page’s memory only.</small></label>}{hasBody && <label>JSON BODY<textarea value={body} onChange={(e)=>setBody(e.target.value)} /></label>}<button className="docs-run" disabled={busy} onClick={run}>{busy ? 'Sending…' : <><Play size={14}/> Send request</>}</button>{response && <div className="try-result"><div className="try-result-head"><b>Response</b><span className={typeof response.status === 'number' && response.status < 400 ? 'ok' : 'fail'}>{response.status}</span></div>{response.url && <small>{response.url}</small>}<pre>{response.text}</pre></div>}<div className="try-disclaimer">Requests go directly to the configured FundFlow API host. Administrator routes require the server key.</div></> : <><p className="try-guide-copy">FundFlow’s read endpoints return data currently stored in the configured database. Choose an endpoint from the navigation to inspect its parameters, response, and examples.</p><button className="docs-run" onClick={() => { selectItem('funds'); setTryOpen(true); }}>Explore fund search <ArrowRight size={14}/></button><div className="try-guide-links"><a href={`${apiBase}/api/openapi.json`} target="_blank" rel="noreferrer">OpenAPI specification <ExternalLink size={13}/></a><a href={`${apiBase}/api/docs`} target="_blank" rel="noreferrer">Interactive API reference <ExternalLink size={13}/></a></div></>}</aside>
    </div><footer className="docs-footer"><span>FundFlow API documentation</span><a href={`${apiBase}/api/openapi.json`}>OpenAPI 3 specification <ExternalLink size={12}/></a></footer>
  </div>;
}

function parameterExample(name) {
  return ({ page:'1', limit:'25', q:'index equity', country:'US', currency:'USD', isin:'US0000000000', category:'Equity', fund_type:'Mutual fund', status:'Active', has_nav:'true', holdings_status:'available', sort:'name', order:'asc', fund_id:'123', source_id:'sec_open_end_fund_classes', from:'2025-01-01', to:'2025-12-31', report_date:'2025-09-30', id:'python-1', run_id:'python-1' })[name] || '—';
}

function describe(id) {
  return ({ health:'Check that the FundFlow API process is responding.', 'db-health':'Verify connectivity to the configured PostgreSQL database.', 'etl-health':'Inspect the most recently recorded ETL run status.', stats:'Read fund, NAV, country, and source counts from the connected database.', countries:'List configured countries and observed fund and NAV coverage.', sources:'List registered sources and their stored record counts.', 'source-detail':'Retrieve one registered source record by its source ID.', 'source-check':'Run a rate-limited connectivity check against a configured official source.', funds:'Search and filter funds stored in FundFlow. Results are paginated.', fund:'Retrieve a fund profile and its latest stored NAV observation.', nav:'Read historical NAV observations for one fund, newest first.', holdings:'Read portfolio holdings for the latest or selected reporting period. Optional financial metrics stay null when unavailable.', runs:'List recent ETL runs and their outcomes.', 'run-detail':'Inspect the result and source-level outcome for one ETL run.', 'start-run':'Queue an ETL run for selected sources or all runnable sources.' })[id] || 'Read data from the FundFlow API.';
}
