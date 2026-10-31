import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, BarChart3, ChevronDown, Database, FileJson2, LayoutDashboard, Menu, Moon, PanelLeftClose, PanelLeftOpen, Sun, Terminal, WalletCards, X } from 'lucide-react';
import { request } from './api';
import ApiDocumentation from './ApiDocumentation.jsx';
import { ApiExplorer, EtlControl, FundExplorer, Overview, Sources } from './DashboardPages.jsx';

const nav = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'explorer', label: 'API explorer', icon: Terminal },
  { id: 'etl', label: 'ETL control', icon: Activity },
  { id: 'funds', label: 'Fund explorer', icon: WalletCards },
  { id: 'sources', label: 'Data sources', icon: Database },
];
function App() {
  const [page, setPage] = useState('overview');
  const [theme, setTheme] = useState(() => localStorage.getItem('fundflow-theme') || 'light');
  const [stats, setStats] = useState(null);
  const [sources, setSources] = useState([]);
  const [countries, setCountries] = useState([]);
  const [runs, setRuns] = useState([]);
  const [funds, setFunds] = useState([]);
  const [health, setHealth] = useState('checking');
  const [loadError, setLoadError] = useState('');
  const [toast, setToast] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, c, r, f, h] = await Promise.all([
        request('/api/v1/stats'), request('/api/v1/sources'), request('/api/v1/countries'),
        request('/api/v1/etl/runs?limit=8'), request('/api/v1/health/database'),
      ]);
      const failed = [s, c, r, f, h].find((result) => !result.response.ok);
      if (failed) throw new Error(failed.body?.error?.message || `API request failed (${failed.response.status})`);
      setStats(s.body?.data || null); setSources(c.body?.data || []); setCountries(r.body?.data || []); setRuns(f.body?.data || []);
      setHealth(h.response.ok ? 'online' : 'degraded');
      const fundPage = await request('/api/v1/funds?limit=6&sort=retrieved_at&order=desc');
      if (!fundPage.response.ok) throw new Error(fundPage.body?.error?.message || `Fund request failed (${fundPage.response.status})`);
      setFunds(fundPage.body?.data || []);
      setLoadError('');
    } catch (error) { setHealth('offline'); setLoadError(error.message || 'Could not load dashboard data from the API.'); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('fundflow-theme', theme); }, [theme]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(''), 3200); return () => clearTimeout(t); }, [toast]);

  if (window.location.pathname.startsWith('/docs')) return <ApiDocumentation />;

  const navigate = (nextPage) => { setPage(nextPage); setSidebarOpen(false); };
  return <div className={`shell ${sidebarOpen ? 'sidebar-open' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
    <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}/>
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand"><div className="brandmark"><BarChart3 size={19}/></div><div><b>FUND<span>FLOW</span></b><small>GLOBAL ETL CONSOLE</small></div><button className="sidebar-close icon-btn" aria-label="Close navigation" onClick={() => setSidebarOpen(false)}><X size={18}/></button></div>
      <div className="workspace-label">WORKSPACE</div>
      <div className="project-chip"><span className="project-icon"><Database size={16}/></span><span><b>Mutual Fund ETL</b><small>PostgreSQL · Python</small></span><ChevronDown size={14}/></div>
      <nav className="side-nav">{nav.map((item) => <button key={item.id} onClick={() => navigate(item.id)} className={page === item.id ? 'active' : ''}><item.icon size={17}/><span>{item.label}</span>{item.id === 'etl' && runs[0]?.status === 'running' && <i className="nav-pulse"/>}</button>)}<a className="side-docs" href="/docs" aria-label="Open API documentation"><FileJson2 size={17}/><span>API documentation</span></a></nav>
      <div className="side-bottom"><div className="side-system"><div className={`status-dot ${health}`}/><div><b>System status</b><small>{health === 'online' ? 'API & database connected' : health === 'checking' ? 'Checking services…' : 'Connection issue'}</small></div><button title="Refresh data" className="icon-btn" onClick={load}><RefreshCw size={14}/></button></div><div className="side-foot"><span>{health === 'online' ? 'DATABASE CONNECTED' : health === 'checking' ? 'CHECKING DATABASE' : 'DATABASE UNAVAILABLE'}</span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><button className="desktop-sidebar-toggle icon-btn" aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!sidebarCollapsed} onClick={() => setSidebarCollapsed(!sidebarCollapsed)}>{sidebarCollapsed ? <PanelLeftOpen size={19}/> : <PanelLeftClose size={19}/>}</button><button className="menu-toggle icon-btn" aria-label="Open navigation" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(true)}><Menu size={19}/></button><a href="/" className="mobile-brand" aria-label="FundFlow home"><span className="mobile-brandmark"><BarChart3 size={16}/></span><b>FUNDFLOW</b></a><div className="crumb"><span>Workspace</span><span className="slash">/</span><b>{nav.find((n) => n.id === page)?.label}</b></div><div className="top-actions"><span className={`live-pill ${health}`}><i/> {health === 'online' ? 'DATABASE ONLINE' : health === 'checking' ? 'CHECKING DATABASE' : 'DATABASE OFFLINE'}</span><button className="theme-toggle icon-btn" title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={16}/> : <Sun size={16}/>}</button><button className="avatar" title="Administrator">A</button></div></header>
      <div className="content">{loadError && <div className="error-box" role="alert">Dashboard data could not be loaded: {loadError}</div>}{page === 'overview' && <Overview stats={stats} sources={sources} countries={countries} runs={runs} funds={funds} onNavigate={setPage} refresh={load}/>} {page === 'explorer' && <ApiExplorer notify={setToast}/>} {page === 'etl' && <EtlControl countries={countries} sources={sources} runs={runs} notify={setToast} refresh={load}/>} {page === 'funds' && <FundExplorer notify={setToast}/>} {page === 'sources' && <Sources sources={sources} refresh={load} notify={setToast}/>}</div>
      <footer className="footer"><span>FundFlow <b>ETL Console</b></span><span>Source registry & data coverage reflect your configured PostgreSQL database.</span><a href="/docs" aria-label="Open FundFlow API documentation">API documentation <ArrowRight size={11}/></a></footer>
    </main>
    {toast && <div className="toast"><CheckCircle2 size={17}/>{toast}<button onClick={() => setToast('')}><XCircle size={15}/></button></div>}
  </div>;
}

export default App;
