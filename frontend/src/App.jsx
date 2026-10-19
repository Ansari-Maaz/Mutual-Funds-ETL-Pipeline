import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowLeft, ArrowRight, BarChart3, Check, CheckCircle2, ChevronDown, CircleHelp, Clock3, Code2, Database, ExternalLink, FileJson2, Filter, Globe2, History, LayoutDashboard, LoaderCircle, Play, RefreshCw, Search, Server, ShieldCheck, Terminal, WalletCards, XCircle } from 'lucide-react';
import { apiBase, request } from './api';

const nav = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'explorer', label: 'API explorer', icon: Terminal },
  { id: 'etl', label: 'ETL control', icon: Activity },
  { id: 'funds', label: 'Fund explorer', icon: WalletCards },
  { id: 'sources', label: 'Data sources', icon: Database },
];
const fmt = (n) => new Intl.NumberFormat('en-US').format(Number(n || 0));
const dt = (v) => v ? new Date(v).toLocaleString() : '—';
const displayRunId = (id) => String(id || '').startsWith('python-') ? String(id) : String(id || '').slice(0,8);
const endpoints = [
  { label: 'Health · API', method: 'GET', path: '/health' },
  { label: 'Health · database', method: 'GET', path: '/api/v1/health/database' },
  { label: 'Countries', method: 'GET', path: '/api/v1/countries' },
  { label: 'Sources', method: 'GET', path: '/api/v1/sources' },
  { label: 'Source detail', method: 'GET', path: '/api/v1/sources/{sourceId}' },
  { label: 'Source connectivity check', method: 'POST', path: '/api/v1/sources/{sourceId}/check' },
  { label: 'Fund list', method: 'GET', path: '/api/v1/funds' },
  { label: 'Fund detail', method: 'GET', path: '/api/v1/funds/{id}' },
  { label: 'NAV history', method: 'GET', path: '/api/v1/funds/{id}/nav' },
  { label: 'Dashboard stats', method: 'GET', path: '/api/v1/stats' },
  { label: 'ETL run history', method: 'GET', path: '/api/v1/etl/runs' },
  { label: 'Trigger ETL run (admin)', method: 'POST', path: '/api/v1/etl/runs', body: '{\n  "all": true\n}' },
];

function App() {
  const [page, setPage] = useState('overview');
  const [stats, setStats] = useState(null);
  const [sources, setSources] = useState([]);
  const [countries, setCountries] = useState([]);
  const [runs, setRuns] = useState([]);
  const [funds, setFunds] = useState([]);
  const [health, setHealth] = useState('checking');
  const [toast, setToast] = useState('');

  const load = useCallback(async () => {
    try {
      const [s, c, r, f, h] = await Promise.all([
        request('/api/v1/stats'), request('/api/v1/sources'), request('/api/v1/countries'),
        request('/api/v1/etl/runs?limit=8'), request('/api/v1/health/database'),
      ]);
      setStats(s.body?.data || null); setSources(c.body?.data || []); setCountries(r.body?.data || []); setRuns(f.body?.data || []);
      setHealth(h.response.ok ? 'online' : 'degraded');
      const fundPage = await request('/api/v1/funds?limit=6&sort=retrieved_at&order=desc');
      setFunds(fundPage.body?.data || []);
    } catch { setHealth('offline'); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(''), 3200); return () => clearTimeout(t); }, [toast]);

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brandmark"><BarChart3 size={19}/></div><div><b>FUND<span>FLOW</span></b><small>GLOBAL ETL CONSOLE</small></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <div className="project-chip"><span className="project-icon"><Database size={16}/></span><span><b>Mutual Fund ETL</b><small>PostgreSQL · Python</small></span><ChevronDown size={14}/></div>
      <nav className="side-nav">{nav.map((item) => <button key={item.id} onClick={() => setPage(item.id)} className={page === item.id ? 'active' : ''}><item.icon size={17}/><span>{item.label}</span>{item.id === 'etl' && runs[0]?.status === 'running' && <i className="nav-pulse"/>}</button>)}</nav>
      <div className="side-bottom"><div className="side-system"><div className={`status-dot ${health}`}/><div><b>System status</b><small>{health === 'online' ? 'API & database connected' : health === 'checking' ? 'Checking services…' : 'Connection issue'}</small></div><button title="Refresh data" className="icon-btn" onClick={load}><RefreshCw size={14}/></button></div><div className="side-foot"><span>BUILD 1.0.0</span><span>·</span><span>LOCAL</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb"><span>Workspace</span><span className="slash">/</span><b>{nav.find((n) => n.id === page)?.label}</b></div><div className="top-actions"><span className="live-pill"><i/> LIVE DATABASE</span><button className="avatar" title="Administrator">A</button></div></header>
      <div className="content">{page === 'overview' && <Overview stats={stats} sources={sources} countries={countries} runs={runs} funds={funds} onNavigate={setPage} refresh={load}/>} {page === 'explorer' && <ApiExplorer notify={setToast}/>} {page === 'etl' && <EtlControl countries={countries} sources={sources} runs={runs} notify={setToast} refresh={load}/>} {page === 'funds' && <FundExplorer notify={setToast}/>} {page === 'sources' && <Sources sources={sources} refresh={load} notify={setToast}/>}</div>
      <footer className="footer"><span>FundFlow <b>ETL Console</b></span><span>Source registry & data coverage reflect your configured PostgreSQL database.</span><a href="https://github.com" onClick={(e) => e.preventDefault()}>Documentation <ExternalLink size={12}/></a></footer>
    </main>
    {toast && <div className="toast"><CheckCircle2 size={17}/>{toast}<button onClick={() => setToast('')}><XCircle size={15}/></button></div>}
  </div>;
}

function PageTitle({ eyebrow, title, desc, actions }) { return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{desc}</p></div>{actions && <div className="title-actions">{actions}</div>}</div>; }
function Metric({ label, value, note, icon: Icon, tone = '' }) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={17}/></span></div><div className="metric-value">{value ?? '—'}</div><div className="metric-note">{note}</div></div>; }
function Status({ value }) { const val = String(value || 'unknown').toLowerCase().replaceAll('_',' '); const cls = ['succeeded','success','integrated','online','reachable'].includes(val) ? 'good' : ['failed','unavailable','error'].includes(val) ? 'bad' : ['running','queued','in progress'].includes(val) ? 'working' : val==='partially succeeded'?'partial':'neutral'; return <span className={`status ${cls}`}><i/>{val.replaceAll('_',' ')}</span>; }
function SectionHeading({ title, sub, action }) { return <div className="section-heading"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{action}</div>; }
function Empty({ children = 'No records yet.' }) { return <div className="empty"><CircleHelp size={18}/><span>{children}</span></div>; }

function Overview({ stats, sources, countries, runs, funds, onNavigate, refresh }) {
  const usable = sources.filter((s) => Number(s.fund_count) > 0);
  const successCountries = countries.filter((country) => Number(country.fund_count) > 0).length;
  const statuses = sources.reduce((acc, s) => { const key = s.latest_check?.status || 'not checked'; acc[key] = (acc[key] || 0) + 1; return acc; }, {});
  const metric = [
    { label: 'Funds in database', value: stats ? fmt(stats.totalFunds) : '…', note: stats ? `${fmt(stats.navObservations)} NAV observations` : 'Loading from PostgreSQL', icon: WalletCards, tone: 'teal' },
    { label: 'Configured countries', value: stats ? fmt(stats.configuredCountries) : '…', note: 'Current country registry', icon: Globe2, tone: 'blue' },
    { label: 'Countries with records', value: countries.length ? fmt(successCountries) : '…', note: 'At least one fund record loaded', icon: Database, tone: 'purple' },
    { label: 'Registered sources', value: stats ? fmt(stats.registeredSources) : '…', note: stats ? `${fmt(stats.integratedSources)} integrated in source catalog` : 'Loading source registry', icon: Server, tone: 'gold' },
  ];
  return <>
    <PageTitle eyebrow="MONITORING / OVERVIEW" title="Global fund data platform" desc="A clear view of what’s flowing through your global fund data pipeline." actions={<><button className="btn btn-quiet" onClick={refresh}><RefreshCw size={15}/> Refresh</button><button className="btn btn-primary" onClick={() => onNavigate('etl')}><Play size={15} fill="currentColor"/> Run ETL</button></>}/>
    <div className="metrics-grid">{metric.map((m) => <Metric key={m.label} {...m}/>)}</div>
    <div className="overview-grid">
      <section className="panel panel-wide"><SectionHeading title="Country coverage" sub="Funds actually stored in the database" action={<button className="text-button" onClick={() => onNavigate('sources')}>All sources <ArrowRight size={14}/></button>}/>
        <div className="coverage-list">{countries.filter((c) => Number(c.fund_count)).sort((a,b) => b.fund_count-a.fund_count).slice(0,8).map((c) => { const percent = usable.length ? Math.round(100 * Number(c.fund_count) / Math.max(...countries.map((x)=>Number(x.fund_count)))) : 0; return <div className="coverage-row" key={c.code}><span className="flag-code">{c.code}</span><span className="coverage-name">{c.name || c.code}<small>{c.region}</small></span><div className="bar-track"><i style={{width:`${percent}%`}}/></div><b className="coverage-count">{fmt(c.fund_count)}</b></div>; })}{!usable.length && <Empty>No country has loaded fund data yet.</Empty>}</div>
      </section>
      <section className="panel"><SectionHeading title="Latest ETL run" sub="Most recent orchestrated run" action={<button className="icon-btn" onClick={refresh}><RefreshCw size={14}/></button>}/>
        {runs[0] ? <div className="latest-run"><div className="run-state"><div className={`run-state-icon ${runs[0].status}`}><Activity size={19}/></div><div><Status value={runs[0].status}/><small>Run ID · {displayRunId(runs[0].id)}</small></div></div><div className="run-meta"><span>Requested</span><b>{dt(runs[0].requested_at)}</b><span>Completed</span><b>{dt(runs[0].finished_at)}</b><span>Last successful</span><b>{dt(stats?.lastSuccessfulRunAt)}</b></div><div className="run-actions"><button className="btn btn-quiet full" onClick={() => onNavigate('etl')}>View run details <ArrowRight size={14}/></button></div></div> : <Empty>No ETL run history yet.</Empty>}
        <div className="check-summary"><div className="check-summary-title">Source connectivity checks</div><div className="check-tags"><span className="tag good">{statuses.reachable || 0} reachable</span><span className="tag bad">{statuses.unavailable || 0} unavailable</span><span className="tag neutral">{statuses['not checked'] || 0} unchecked</span></div><small>Reachability does not confirm valid fund data.</small></div>
      </section>
      <section className="panel panel-wide"><SectionHeading title="Recent runs" sub="Execution history with real process outcomes" action={<button className="text-button" onClick={() => onNavigate('etl')}>View history <ArrowRight size={14}/></button>}/><RunsTable runs={runs.slice(0,5)} compact/></section>
      <section className="panel"><SectionHeading title="Latest fund records" sub="Recently retrieved from source feeds" action={<button className="text-button" onClick={() => onNavigate('funds')}>Browse <ArrowRight size={14}/></button>}/><div className="mini-funds">{funds.slice(0,5).map((f)=><div className="mini-fund" key={f.id}><div className="fund-avatar">{(f.name||'?').slice(0,1)}</div><div className="mini-fund-name"><b>{f.name}</b><small>{f.country||'Country n/a'} · {f.sourceId}</small></div><span>{f.currency||'—'}</span></div>)}{!funds.length&&<Empty>No fund records found.</Empty>}</div></section>
    </div>
  </>;
}

function RunsTable({ runs, compact=false, onSelect }) { return <div className="table-wrap"><table><thead><tr><th>RUN ID</th><th>STATUS</th><th>SOURCES</th><th>REQUESTED</th><th>FINISHED</th></tr></thead><tbody>{runs.map((r)=><tr key={r.id} className={onSelect?'click-row':''} onClick={()=>onSelect?.(r)}><td className="mono">{displayRunId(r.id)}</td><td><Status value={r.status}/></td><td>{(r.source_ids||[]).length}</td><td>{dt(r.requested_at)}</td><td>{dt(r.finished_at)}</td></tr>)}</tbody></table>{!runs.length&&<Empty>No ETL runs to show.</Empty>}</div>; }

function ApiExplorer({ notify }) {
  const [index, setIndex] = useState(0); const [method, setMethod] = useState(endpoints[0].method); const [pathValue, setPathValue] = useState(endpoints[0].path); const [params, setParams] = useState(''); const [body, setBody] = useState(''); const [apiKey, setApiKey] = useState(''); const [result, setResult] = useState(null); const [busy, setBusy] = useState(false);
  const select = (i) => { setIndex(i); setMethod(endpoints[i].method); setPathValue(endpoints[i].path); setBody(endpoints[i].body || ''); setResult(null); };
  const send = async () => {
    const route = pathValue.replace('{sourceId}', 'cvm_open_fund_data').replace('{id}', '1');
    let target = route;
    try { const url = new URL(route, apiBase); for (const line of params.split(/\r?\n/)) { const split = line.indexOf('='); if (split > 0) url.searchParams.set(line.slice(0,split).trim(),line.slice(split+1).trim()); } target = `${url.pathname}${url.search}`; } catch { setResult({status:0,elapsed:0,body:{error:{message:'Enter a valid path'}}}); return; }
    setBusy(true);
    try { const response = await request(target, { method, headers: apiKey ? {'X-API-Key':apiKey} : {}, ...(method === 'POST' ? {body: body || '{}'} : {}) }); setResult({status:response.response.status,elapsed:response.elapsed,body:response.body,headers:Object.fromEntries(response.response.headers.entries())}); }
    catch (error) { setResult({status:0,elapsed:0,body:{error:{message:error.message}}}); }
    finally { setBusy(false); }
  };
  const copy = async () => { await navigator.clipboard.writeText(JSON.stringify(result?.body ?? null,null,2)); notify('Response JSON copied.'); };
  return <><PageTitle eyebrow="DEVELOPER TOOLS / API EXPLORER" title="Make a request" desc="Try the project’s fixed API routes and inspect real response codes, timings and JSON." actions={<span className="secure-note"><ShieldCheck size={15}/> Project endpoints only</span>}/>
    <div className="explorer-layout"><section className="panel request-panel"><div className="panel-kicker"><Code2 size={15}/> REQUEST BUILDER</div><label className="field-label">PREDEFINED ENDPOINT</label><select className="input" value={index} onChange={(e)=>select(Number(e.target.value))}>{endpoints.map((e,i)=><option key={e.path+i} value={i}>{e.label}</option>)}</select><div className="request-line"><select className="method-select" value={method} onChange={(e)=>setMethod(e.target.value)}><option>GET</option><option>POST</option></select><input className="input mono" value={pathValue} readOnly aria-label="API path"/></div><label className="field-label">QUERY PARAMETERS <span>key=value pairs, one per line</span></label><textarea className="code-input small-code" value={params} onChange={(e)=>setParams(e.target.value)} placeholder={'limit=25\npage=1'} rows="3"/><label className="field-label">REQUEST BODY <span>POST endpoints only</span></label><textarea className="code-input" value={body} onChange={(e)=>setBody(e.target.value)} placeholder="{}" rows="6" disabled={method!=='POST'}/>{pathValue.includes('/etl/runs') && <><label className="field-label">ADMIN API KEY</label><input type="password" className="input" value={apiKey} onChange={(e)=>setApiKey(e.target.value)} placeholder="X-API-Key" autoComplete="off"/></>}<div className="request-footer"><span><i className="api-dot"/>{new URL(apiBase).host}</span><button className="btn btn-primary" onClick={send} disabled={busy}>{busy?<LoaderCircle size={15} className="spin"/>:<Play size={15} fill="currentColor"/>} Send request</button></div></section>
    <section className="panel response-panel"><div className="response-head"><div><div className="panel-kicker"><Activity size={15}/> RESPONSE</div><h2>{result ? 'Response received' : 'Ready when you are'}</h2></div>{result && <div className="response-meta"><span className={result.status>=200&&result.status<300?'status-code good':'status-code bad'}>{result.status || 'ERR'}</span><span>{result.elapsed} ms</span><button className="icon-btn" onClick={copy} title="Copy response JSON"><FileJson2 size={15}/></button></div>}</div>{result ? <><div className="response-toolbar"><span>BODY · JSON</span><span>{JSON.stringify(result.body||{}).length} bytes</span></div><pre className="json-response">{JSON.stringify(result.body,null,2)}</pre>{result.headers&&<details className="headers-details"><summary>Response headers</summary><pre>{JSON.stringify(result.headers,null,2)}</pre></details>}</> : <div className="response-empty"><div className="response-symbol">{`{ }`}</div><h3>Your response will appear here</h3><p>Select an endpoint, adjust the request and send it to see the live API response.</p></div>}</section></div>
  </>;
}

function EtlControl({ countries, sources, runs, notify, refresh }) {
  const [selected, setSelected] = useState([]); const [all, setAll] = useState(true); const [key, setKey] = useState(''); const [current, setCurrent] = useState(null); const [detail, setDetail] = useState(null); const [busy, setBusy] = useState(false);
  useEffect(()=>{ if (runs[0] && (!current || runs[0].id === current.id)) setCurrent(runs[0]); },[runs]);
  useEffect(()=>{ if(!current?.id) return; let live=true; const loadRun=async()=>{try{const res=await request(`/api/v1/etl/runs/${current.id}`);if(live&&res.body?.data){setDetail(res.body.data); if(['queued','running'].includes(res.body.data.status)) setTimeout(()=>refresh(),2500);}}catch{}}; loadRun();return()=>{live=false}; },[current?.id,current?.status,refresh]);
  const connectorSources = sources.filter((s)=>s.integration_status==='Integrated' || s.source_id && ['cvm_open_fund_data','csrc_public_fund_index','gsfm_unit_prices','asisa_cis_fund_list','finma_swiss_fund_list','fca_authorised_funds','sec_open_end_fund_classes','cnmv_spanish_fund_register','fi_sweden_ucits_holdings','cbi_authorised_ucits','amf_geco'].includes(s.source_id));
  const countryNames = new Map(countries.map((country)=>[country.code,country.name]));
  const connectorCountries = [...new Set(connectorSources.map((source)=>source.country_code))].sort();
  const toggle = (id) => setSelected((items)=>items.includes(id)?items.filter((x)=>x!==id):[...items,id]);
  const start = async () => {
    if (!key) { notify('Enter the admin API key to enable ETL controls.'); return; }
    if (!window.confirm(all ? 'Start an ETL run for all configured connectors?' : `Start ETL for ${selected.length} selected country/countries?`)) return;
    setBusy(true);
    try { const response=await request('/api/v1/etl/runs',{method:'POST',headers:{'X-API-Key':key},body:JSON.stringify(all?{all:true}:{countryCodes:selected})}); if(!response.response.ok) throw new Error(response.body?.error?.message||`HTTP ${response.response.status}`); setCurrent(response.body.data); setDetail(response.body.data); notify(`ETL run queued · ${displayRunId(response.body.data.id)}`); await refresh(); }
    catch(error){notify(`Could not queue ETL run: ${error.message}`);} finally{setBusy(false);}
  };
  const outcomes = detail?.results || [];
  return <><PageTitle eyebrow="OPERATIONS / ETL CONTROL" title="Run the pipeline" desc="Trigger registered Python connectors, follow progress, then inspect stdout, failures and source-level outcomes." actions={<button className="btn btn-quiet" onClick={refresh}><RefreshCw size={15}/> Refresh status</button>}/>
    <div className="etl-layout"><section className="panel control-panel"><div className="panel-kicker"><Play size={15}/> NEW ETL RUN</div><div className="all-switch"><div><b>Run all sources</b><small>Execute every registered connector in configured order.</small></div><button role="switch" aria-checked={all} className={`switch ${all?'on':''}`} onClick={()=>setAll(!all)}><i/></button></div><label className="field-label">OR SELECT COUNTRIES</label><div className={`source-select-list ${all?'disabled':''}`}>{connectorCountries.map(code=><label className="source-select-row" key={code}><input type="checkbox" disabled={all} checked={selected.includes(code)} onChange={()=>toggle(code)}/><span className="source-country">{code}</span><span className="source-select-name"><b>{countryNames.get(code)||code}</b><small>{connectorSources.filter((source)=>source.country_code===code).map((source)=>source.source_name).join(' · ')}</small></span><span className="source-record-count">{fmt(connectorSources.filter((source)=>source.country_code===code).reduce((sum,source)=>sum+Number(source.fund_count||0),0))} funds</span></label>)}{!connectorCountries.length&&<Empty>Source registry did not load.</Empty>}</div><label className="field-label">ADMIN API KEY <span>kept in memory only</span></label><input className="input" type="password" value={key} onChange={(e)=>setKey(e.target.value)} placeholder="Set ADMIN_API_KEY on the API server" autoComplete="off"/><button className="btn btn-primary full start-button" disabled={busy || (!all&&!selected.length)} onClick={start}>{busy?<LoaderCircle size={15} className="spin"/>:<Play size={15} fill="currentColor"/>} {busy?'Starting…':'Start ETL run'}</button><div className="security-hint"><ShieldCheck size={15}/><span>Runs require an admin key. Only registered Python connector IDs are accepted.</span></div></section>
      <div className="etl-main"><section className="panel current-panel"><SectionHeading title="Current run" sub={current?`Run ID · ${current.id}`:'No run selected'}/>{current?<><div className="current-state"><div className={`run-state-icon ${detail?.status||current.status}`}><Activity size={19}/></div><div><Status value={detail?.status||current.status}/><p>{(detail?.source_ids||current.sourceIds||[]).length} source connectors · {detail?.records_loaded!=null?`${fmt(detail.records_loaded)} loaded (legacy run)`:((detail?.results||[]).length+' outcomes reported')}</p></div><div className="run-time"><small>Started</small><b>{dt(detail?.started_at||current.startedAt)}</b><small>Completed</small><b>{dt(detail?.finished_at)}</b></div></div>{outcomes.length>0&&<div className="outcome-list">{outcomes.map((r)=><div className="outcome" key={r.source_id}><span className="outcome-icon">{r.status==='Succeeded'?<Check size={14}/>:<XCircle size={14}/>}</span><b>{r.source_id}</b><Status value={r.status}/><span className="outcome-count">{fmt(r.records_extracted)} extracted</span><span className="outcome-count">{fmt(r.records_loaded)} loaded</span><span className="outcome-count">{fmt(r.navs_loaded)} NAV</span><span className="outcome-count">{fmt(r.rejected_records)} rejected</span>{r.error&&<small className="outcome-error">{r.error}</small>}</div>)}</div>}{detail?.error&&<div className="error-box">{detail.error}</div>}</>:<Empty>Start a run or choose an entry from recent history.</Empty>}{detail?.stdout&&<details className="log-details"><summary><Terminal size={14}/> Standard output</summary><pre>{detail.stdout}</pre></details>}{detail?.stderr&&<details className="log-details error-log"><summary><Terminal size={14}/> Standard error</summary><pre>{detail.stderr}</pre></details>}</section>
        <section className="panel"><SectionHeading title="Run history" sub="Select a row to inspect that run" action={<button className="icon-btn" onClick={refresh}><RefreshCw size={14}/></button>}/><RunsTable runs={runs} onSelect={(run)=>{setCurrent(run);setDetail(null);}}/></section></div></div>
  </>;
}

function FundExplorer({ notify }) {
  const [data,setData]=useState([]);const [pagination,setPagination]=useState({page:1,limit:25,total:0,pages:0});const [filters,setFilters]=useState({q:'',country:'',currency:'',source:''});const [countries,setCountries]=useState([]);const [sources,setSources]=useState([]);const [busy,setBusy]=useState(false);const [selected,setSelected]=useState(null);const [navRows,setNavRows]=useState([]);
  const load=useCallback(async(page=1)=>{setBusy(true);const q=new URLSearchParams({page,limit:25,sort:'name'});Object.entries(filters).forEach(([k,v])=>v&&q.set(k,v));try{const result=await request(`/api/v1/funds?${q}`);if(!result.response.ok)throw new Error(result.body?.error?.message);setData(result.body.data||[]);setPagination(result.body.pagination||pagination);}catch(error){notify(error.message);}finally{setBusy(false);}},[filters]);
  useEffect(()=>{load(1);request('/api/v1/countries').then(r=>setCountries(r.body?.data||[]));request('/api/v1/sources').then(r=>setSources(r.body?.data||[]));},[load]);
  const openFund=async(f)=>{setSelected(f);setNavRows([]);const r=await request(`/api/v1/funds/${f.id}/nav?limit=100`);if(r.response.ok)setNavRows(r.body.data||[]);};
  const exportCsv=()=>{const cols=['id','name','country','currency','isin','sourceId','sourceFundId'];const lines=[cols.join(','),...data.map(row=>cols.map(c=>`"${String(row[c]??'').replaceAll('"','""')}"`).join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));a.download='fund-results.csv';a.click();URL.revokeObjectURL(a.href);};
  return <><PageTitle eyebrow="DATA / FUND EXPLORER" title="Explore fund records" desc="Search, filter and export real records persisted in the shared PostgreSQL database." actions={<button className="btn btn-quiet" onClick={exportCsv}><ArrowDownToLine size={15}/> Export this page</button>}/>
    <section className="panel fund-panel"><div className="filter-row"><div className="searchbox"><Search size={16}/><input value={filters.q} placeholder="Search fund name…" onChange={(e)=>setFilters({...filters,q:e.target.value})}/></div><select className="input filter-select" value={filters.country} onChange={(e)=>setFilters({...filters,country:e.target.value})}><option value="">All countries</option>{countries.map(c=><option value={c.code} key={c.code}>{c.name||c.code}</option>)}</select><select className="input filter-select" value={filters.source} onChange={(e)=>setFilters({...filters,source:e.target.value})}><option value="">All sources</option>{sources.map(s=><option value={s.source_id} key={s.source_id}>{s.country_code} · {s.organization}</option>)}</select><input className="input currency-filter" maxLength="3" placeholder="Currency" value={filters.currency} onChange={(e)=>setFilters({...filters,currency:e.target.value.toUpperCase()})}/><span className="total-count">{fmt(pagination.total)} results</span></div>
      <div className="table-wrap"><table className="fund-table"><thead><tr><th>FUND NAME</th><th>COUNTRY</th><th>CURRENCY</th><th>ISIN</th><th>SOURCE</th><th></th></tr></thead><tbody>{data.map(f=><tr key={f.id} onClick={()=>openFund(f)} className="click-row"><td><b>{f.name}</b><small className="subcell">ID {f.sourceFundId}</small></td><td><span className="country-badge">{f.country||'—'}</span></td><td>{f.currency||'—'}</td><td className="mono">{f.isin||'—'}</td><td className="source-id-cell">{f.sourceId}</td><td><ArrowRight size={14}/></td></tr>)}</tbody></table>{busy&&<div className="table-loading"><LoaderCircle className="spin" size={17}/> Loading from database…</div>}{!busy&&!data.length&&<Empty>No funds match these filters.</Empty>}</div>
      <div className="pagination"><span>Page {pagination.page} of {Math.max(1,pagination.pages)}</span><div><button className="btn btn-quiet" disabled={pagination.page<=1||busy} onClick={()=>load(pagination.page-1)}><ArrowLeft size={14}/> Previous</button><button className="btn btn-quiet" disabled={pagination.page>=pagination.pages||busy} onClick={()=>load(pagination.page+1)}>Next <ArrowRight size={14}/></button></div></div>
    </section>
    {selected&&<div className="modal-backdrop" onClick={()=>setSelected(null)}><section className="fund-modal" onClick={(e)=>e.stopPropagation()}><button className="modal-close icon-btn" onClick={()=>setSelected(null)}><XCircle size={17}/></button><div className="eyebrow">FUND RECORD · #{selected.id}</div><h2>{selected.name}</h2><p>{selected.sourceId} · {selected.country||'Country not set'}</p><div className="detail-grid"><div><small>Source identifier</small><b>{selected.sourceFundId}</b></div><div><small>ISIN</small><b>{selected.isin||'Not available'}</b></div><div><small>Currency</small><b>{selected.currency||'Not available'}</b></div><div><small>Added</small><b>{dt(selected.retrievedAt)}</b></div></div><SectionHeading title="NAV history" sub="Stored observations only"/>{navRows.length?<div className="nav-list">{navRows.map(n=><div key={n.id}><span>{String(n.valuation_date).slice(0,10)}</span><b>{n.nav} {n.currency}</b></div>)}</div>:<Empty>No NAV observations are stored for this fund.</Empty>}</section></div>}
  </>;
}

function Sources({ sources, refresh, notify }) {
  const [busy,setBusy]=useState('');const [filter,setFilter]=useState('');const rows=useMemo(()=>sources.filter(s=>`${s.country_code} ${s.organization} ${s.source_name} ${s.source_id}`.toLowerCase().includes(filter.toLowerCase())),[sources,filter]);
  const check=async(id)=>{setBusy(id);try{const r=await request(`/api/v1/sources/${id}/check`,{method:'POST'});if(r.body?.data){notify(`HTTP ${r.body.data.httpStatus||'—'} · ${r.body.data.status} · ${r.body.data.responseTimeMs} ms`);await refresh();}else notify(r.body?.error?.message||`HTTP ${r.response.status}`);}catch(e){notify(e.message)}finally{setBusy('')}};
  return <><PageTitle eyebrow="REGISTRY / DATA SOURCES" title="Know your sources" desc="Official-source registry, ingestion coverage and last connectivity check. A reachable endpoint alone is not a successful load." actions={<button className="btn btn-quiet" onClick={refresh}><RefreshCw size={15}/> Refresh</button>}/>
    <section className="panel sources-panel"><div className="filter-row"><div className="searchbox"><Search size={16}/><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Search countries or providers…"/></div><span className="total-count">{rows.length} registered sources</span></div><div className="table-wrap"><table><thead><tr><th>COUNTRY / SOURCE</th><th>INGESTION</th><th>FUNDS</th><th>NAV</th><th>LAST CONNECTIVITY</th><th>FORMAT</th><th></th></tr></thead><tbody>{rows.map(s=><tr key={s.source_id}><td><div className="source-cell"><span className="source-country">{s.country_code}</span><span><b>{s.organization}</b><small>{s.source_name}</small><a href={s.official_website||s.endpoint_url} target="_blank" rel="noreferrer">Official source <ExternalLink size={11}/></a></span></div></td><td><Status value={s.integration_status}/></td><td>{fmt(s.fund_count)}</td><td>{fmt(s.nav_count)}</td><td>{s.latest_check?<><Status value={s.latest_check.status}/><small className="subcell">HTTP {s.latest_check.http_status||'—'} · {s.latest_check.response_time_ms||'—'} ms · {dt(s.latest_check.checked_at)}</small></>:<span className="muted">Not checked</span>}</td><td className="format-cell">{s.response_format||'—'}</td><td><button className="btn btn-quiet check-btn" onClick={()=>check(s.source_id)} disabled={busy===s.source_id}>{busy===s.source_id?<LoaderCircle size={14} className="spin"/>:<RefreshCw size={14}/>} Check</button></td></tr>)}</tbody></table>{!rows.length&&<Empty>No registered sources match this search.</Empty>}</div></section>
  </>;
}

export default App;
