import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, ArrowRight, BadgeCheck, Building2, CalendarDays, ChevronDown, ChevronRight,
  CircleDollarSign, Database, ExternalLink, FileJson2, FileText, Gauge, Globe2, Hash,
  Info, Layers, LoaderCircle, PieChart, RefreshCw, Search, ShieldCheck, TrendingUp,
  WalletCards,
} from 'lucide-react';
import { request } from './api';
import { fmtNumber, money, dt, displayText, statusClass, statusLabel } from './dashboardFormat';

const NA = 'Not available from source';

const ASSET_CLASS_LABELS = {
  EC: 'Common equity', EP: 'Preferred equity', DBT: 'Debt', 'ABS-MBS': 'Mortgage-backed',
  'ABS-O': 'Asset-backed', 'ABS-CBDO': 'Collateralized debt obligation',
  'ABS-APCP': 'Asset-backed commercial paper', LON: 'Loan', SN: 'Structured note',
  STIV: 'Short-term investment', RA: 'Repurchase agreement', RE: 'Real estate',
  COMM: 'Commodity', DE: 'Derivative', DFE: 'FX derivative', DIR: 'Rate derivative',
  DCR: 'Commodity derivative', DCO: 'Credit derivative', DO: 'Derivative', OTHER: 'Other',
};
const ISSUER_TYPE_LABELS = {
  CORP: 'Corporate', UST: 'U.S. Treasury', USGA: 'U.S. government agency',
  USGSE: 'U.S. government-sponsored', MUN: 'Municipal', NUSS: 'Non-U.S. sovereign',
  RF: 'Registered fund', PF: 'Private fund', OTHER: 'Other',
};
const UNIT_LABELS = { NS: 'shares', PA: 'principal', NC: 'contracts', OU: 'other units' };
const signedPct = (value, digits = 2) => value == null ? '—'
  : `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(digits)}%`;
const peText = (value) => value == null ? '—' : `${Number(value).toFixed(1)}×`;

function Section({ id, icon: Icon, title, sub, action, children }) {
  return <section className="panel profile-section" id={id}>
    <div className="section-heading">
      <div className="pf-section-title"><span className="pf-section-icon">{Icon ? <Icon size={15} /> : <Layers size={15} />}</span><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div></div>
      {action}
    </div>
    {children}
  </section>;
}

function Field({ label, value, mono, title }) {
  const present = value !== null && value !== undefined && value !== '';
  return <div className="pf-field" title={title || label}><small>{label}</small><b className={present ? (mono ? 'mono' : '') : 'pf-na'}>{present ? (typeof value === 'object' ? JSON.stringify(value) : String(value)) : NA}</b></div>;
}

function Empty({ children }) { return <div className="empty">{children}</div>; }

function Status({ value }) {
  const cls = statusClass(value);
  return <span className={`status ${cls}`}><i />{statusLabel(value)}</span>;
}

function KeyMetric({ label, value, note, icon: Icon }) {
  return <div className="pf-metric"><div className="pf-metric-top"><span>{label}</span>{Icon && <Icon size={14} />}</div><b>{value}</b>{note && <small>{note}</small>}</div>;
}

function JsonBlock({ value, maxHeight = 300 }) {
  return <pre className="pf-json" style={{ maxHeight }}>{JSON.stringify(value, null, 2)}</pre>;
}

function SectionNav({ sections, active, onJump }) {
  return <div className="pf-section-nav">
    {sections.map((s) => <button key={s.id} className={active === s.id ? 'active' : ''} onClick={() => onJump(s.id)}>{s.label}</button>)}
  </div>;
}

export default function FundProfile({ fundId: initialId, onBack, onOpenFund }) {
  const [fundId, setFundId] = useState(initialId || '');
  const [fund, setFund] = useState(null);
  const [nav, setNav] = useState([]);
  const [profileData, setProfileData] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [completeness, setCompleteness] = useState(null);
  const [mutual, setMutual] = useState(null);
  const [holdings, setHoldings] = useState([]);
  const [reportDates, setReportDates] = useState([]);
  const [reportDate, setReportDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [datasetFilter, setDatasetFilter] = useState('all');
  const [activeSection, setActiveSection] = useState('identity');
  const [rawOpen, setRawOpen] = useState(false);
  const searchTimer = useRef(null);

  const loadFund = useCallback(async (id) => {
    if (!/^\d+$/.test(String(id))) { setError('Enter a numeric fund id.'); return; }
    setLoading(true); setError('');
    try {
      const [detail, navRes, profileRes, compRes, holdRes] = await Promise.all([
        request(`/api/v1/funds/${id}`),
        request(`/api/v1/funds/${id}/nav?limit=1000`),
        request(`/api/v1/funds/${id}/profile-data?limit=500`),
        request(`/api/v1/funds/${id}/completeness`),
        request(`/api/v1/funds/${id}/holdings?limit=2000`),
      ]);
      const failed = [detail, navRes, profileRes, compRes, holdRes].find((r) => !r.response.ok);
      if (failed) throw new Error(failed.body?.error?.message || `Request failed (${failed.response.status})`);
      const f = detail.body.data;
      setFund(f); setNav(navRes.body.data || []);
      setProfileData(profileRes.body.data || []); setDatasets(profileRes.body.datasets || []);
      setCompleteness(compRes.body.data || null);
      setHoldings(holdRes.body.data || []);
      setReportDates(holdRes.body.reportDates || []);
      setReportDate(holdRes.body.reportDate || holdRes.body.reportDates?.[0] || '');
      setDatasetFilter('all');
      setError('');
      // Normalized publisher profile (best-effort; requires a ticker).
      setMutual(null);
      if (f?.ticker) {
        request(`/api/v1/mutual_funds/world?symbol=${encodeURIComponent(f.ticker)}`).then((r) => {
          if (r.response.ok && r.body?.mutual_fund) setMutual(r.body);
        }).catch(() => {});
      }
    } catch (e) { setError(e.message || 'Could not load fund data.'); setFund(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (fundId) loadFund(fundId); }, [fundId, loadFund]);

  const runSearch = useCallback(async (q) => {
    setSearch(q);
    clearTimeout(searchTimer.current);
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const r = await request(`/api/v1/funds?q=${encodeURIComponent(q.trim())}&limit=12&sort=name&order=asc`);
        setResults(r.response.ok ? (r.body.data || []) : []);
      } catch { setResults([]); }
      finally { setSearching(false); }
    }, 250);
  }, []);

  const chooseFund = (f) => { setFundId(String(f.id)); setResults([]); setSearch(''); onOpenFund?.(f.id); };

  const grouped = useMemo(() => {
    const map = new Map();
    for (const row of profileData) {
      if (!map.has(row.dataset)) map.set(row.dataset, []);
      map.get(row.dataset).push(row);
    }
    return map;
  }, [profileData]);
  const visibleDatasets = datasetFilter === 'all' ? [...grouped.keys()].sort() : [datasetFilter];

  const sections = useMemo(() => {
    const list = [
      { id: 'identity', label: 'Identity' },
      { id: 'metrics', label: 'Key metrics' },
      { id: 'nav', label: 'NAV history' },
      { id: 'snapshots', label: 'Profile data' },
    ];
    if (holdings.length) list.push({ id: 'holdings', label: 'Holdings' });
    if (mutual) list.push({ id: 'normalized', label: 'Normalized view' });
    if (completeness) list.push({ id: 'completeness', label: 'Completeness' });
    return list;
  }, [holdings.length, mutual, completeness]);

  const jump = (id) => {
    setActiveSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const changeReportDate = async (date) => {
    setReportDate(date); setLoading(true);
    try {
      const r = await request(`/api/v1/funds/${fundId}/holdings?report_date=${encodeURIComponent(date)}&limit=2000`);
      if (r.response.ok) setHoldings(r.body.data || []);
    } catch { /* keep current rows */ } finally { setLoading(false); }
  };

  const changingFund = () => { setFund(null); setNav([]); setProfileData([]); setHoldings([]); setMutual(null); setCompleteness(null); };

  return <div className="fund-profile-page">
    <div className="pf-topbar">
      <button className="btn btn-quiet" onClick={() => { onBack?.(); }}><ArrowLeft size={14} /> Dashboard</button>
      <div className="pf-search-wrap">
        <div className="searchbox"><Search size={15} /><input value={search} onChange={(e) => runSearch(e.target.value)} placeholder="Find a fund by name or ticker…" aria-label="Search funds" /></div>
        {searching && <span className="pf-search-hint"><LoaderCircle size={13} className="spin" /> Searching…</span>}
        {results.length > 0 && <div className="pf-search-results">
          {results.map((r) => <button key={r.id} onClick={() => chooseFund(r)}><span className="pf-result-ticker">{r.ticker || r.symbol || '—'}</span><span className="pf-result-name">{r.name}<small>{r.provider || r.country || 'Fund'}</small></span><ArrowRight size={13} /></button>)}
        </div>}
      </div>
      <div className="pf-id-box"><label>FUND ID</label><input className="input" value={fundId} onChange={(e) => setFundId(e.target.value)} placeholder="e.g. 254737" onKeyDown={(e) => { if (e.key === 'Enter') loadFund(fundId); }} /><button className="btn btn-primary" onClick={() => loadFund(fundId)} disabled={loading}>{loading ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />} Load</button></div>
    </div>

    {error && <div className="error-box" role="alert">{error}</div>}

    {!fund && !loading && <div className="panel pf-empty-state"><WalletCards size={34} /><h2>Fund profile</h2><p>Search for a fund above, or enter its numeric FundFlow id, to open a complete profile with every stored field, NAV history, filed holdings and source provenance.</p></div>}
    {loading && !fund && <div className="panel table-loading"><LoaderCircle size={18} className="spin" /> Loading complete fund profile…</div>}

    {fund && <>
      <div className="pf-hero">
        <div className="pf-hero-main">
          <div className="eyebrow">FUND PROFILE · ID {fund.id}</div>
          <h1>{fund.name}</h1>
          <div className="pf-hero-meta">
            {fund.ticker && <span className="pf-pill ticker">{fund.ticker}</span>}
            {fund.isin && <span className="pf-pill mono">{fund.isin}</span>}
            {fund.fundType && <span className="pf-pill">{fund.fundType}</span>}
            {fund.country && <span className="pf-pill"><Globe2 size={11} /> {fund.country}</span>}
            {fund.status && <span className="pf-pill"><ShieldCheck size={11} /> {fund.status}</span>}
          </div>
          <p>{fund.provider || fund.source?.organization || '—'} · {fund.category || 'No publisher category'} · {fund.currency || 'Currency not set'}</p>
          <div className="pf-hero-links">
            {fund.officialUrl && <a href={fund.officialUrl} target="_blank" rel="noreferrer">Official fund page <ExternalLink size={12} /></a>}
            {fund.source?.url && <a href={fund.source.url} target="_blank" rel="noreferrer">Source endpoint <ExternalLink size={12} /></a>}
            <button className="text-button" onClick={() => setRawOpen(!rawOpen)}><FileJson2 size={13} /> {rawOpen ? 'Hide' : 'Show'} full raw JSON</button>
          </div>
        </div>
        <div className="pf-hero-side">
          <div className="pf-source-card"><small>SOURCE</small><b>{fund.source?.organization || fund.sourceId}</b><span>{fund.source?.name || '—'}</span><small className="mono">{fund.sourceFundId}</small></div>
        </div>
      </div>

      {rawOpen && <section className="panel"><div className="section-heading"><div className="pf-section-title"><span className="pf-section-icon"><FileJson2 size={15} /></span><div><h2>Full raw record</h2><p>Every field returned by the fund detail endpoint, plus all linked datasets.</p></div></div></div><JsonBlock value={{ fund, navObservations: nav.slice(0, 50), profileData, completeness, mutualFundView: mutual }} maxHeight={520} /></section>}

      <SectionNav sections={sections} active={activeSection} onJump={jump} />

      <Section id="identity" icon={BadgeCheck} title="Identity & reference" sub="Every scalar field stored on the fund record; empty fields stay null rather than inferred.">
        <div className="pf-field-grid">
          <Field label="Fund id" value={fund.id} mono />
          <Field label="Source fund id" value={fund.sourceFundId} mono />
          <Field label="Source id" value={fund.sourceId} mono />
          <Field label="Name" value={fund.name} />
          <Field label="Legal name" value={fund.legalName} />
          <Field label="Ticker / symbol" value={fund.ticker || fund.symbol} mono />
          <Field label="ISIN" value={fund.isin} mono />
          <Field label="Series LEI" value={fund.lei} mono />
          <Field label="Provider / family" value={fund.provider} />
          <Field label="Fund type" value={fund.fundType || fund.instrument_type} />
          <Field label="Category" value={fund.category} />
          <Field label="Currency" value={fund.currency} />
          <Field label="Currency basis" value={fund.currencyBasis} />
          <Field label="Inception date" value={fund.inceptionDate} />
          <Field label="Domicile country" value={fund.domicileCountry || fund.country} />
          <Field label="Source country" value={fund.sourceCountry} />
          <Field label="Country basis" value={fund.countryBasis} />
          <Field label="Status" value={fund.status} />
          <Field label="Manager" value={fund.manager} />
          <Field label="Administrator" value={fund.administrator} />
          <Field label="Target audience" value={fund.targetAudience} />
          <Field label="Net assets" value={fund.netAssets != null ? money(fund.netAssets, fund.currency || 'USD') : null} />
          <Field label="Net assets date" value={fund.netAssetsDate} />
          <Field label="Official URL" value={fund.officialUrl} />
          <Field label="Holdings status" value={fund.holdingsStatus} />
          <Field label="Holdings report date" value={fund.holdingsReportDate} />
          <Field label="Last retrieved" value={dt(fund.retrievedAt)} />
        </div>
        {fund.market_data_sources && <div className="pf-sub"><small>MARKET DATA SOURCES</small><JsonBlock value={fund.market_data_sources} maxHeight={160} /></div>}
      </Section>

      <Section id="metrics" icon={Gauge} title="Key metrics" sub="Latest stored valuation and reported fundamentals.">
        <div className="pf-metrics">
          <KeyMetric icon={CircleDollarSign} label="Latest NAV" value={fund.latestNav ? money(fund.latestNav.value, fund.latestNav.currency || fund.currency || 'USD') : NA} note={fund.latestNav ? `${fund.latestNav.date} · ${fund.latestNav.sourceId || 'source not recorded'}` : 'No stored observation'} />
          <KeyMetric icon={TrendingUp} label="Net assets" value={fund.netAssets != null ? money(fund.netAssets, fund.currency || 'USD') : NA} note={fund.netAssetsDate || 'No report date'} />
          <KeyMetric icon={CalendarDays} label="Inception" value={fund.inceptionDate || NA} note="Share-class inception where filed" />
          <KeyMetric icon={PieChart} label="NAV observations" value={fmtNumber(nav.length)} note={nav.length ? `${nav[nav.length - 1]?.valuation_date} → ${nav[0]?.valuation_date}` : 'No history'} />
        </div>
        {fund.latestNav?.sourceUrl && <p className="pf-source-link"><a href={fund.latestNav.sourceUrl} target="_blank" rel="noreferrer">Open latest NAV source <ExternalLink size={11} /></a></p>}
      </Section>

      <Section id="nav" icon={TrendingUp} title="NAV history" sub={`${nav.length} stored observations, newest first. Source and valuation basis retained per row.`}>
        {nav.length ? <div className="table-wrap pf-table"><table><thead><tr><th>VALUATION DATE</th><th>NAV</th><th>CURRENCY</th><th>OPEN</th><th>HIGH</th><th>LOW</th><th>CLOSE</th><th>BASIS</th><th>SOURCE</th></tr></thead><tbody>
          {nav.map((n) => <tr key={n.id}><td className="mono">{String(n.valuation_date).slice(0, 10)}</td><td><b>{Number(n.nav).toFixed(4)}</b></td><td>{n.currency || '—'}</td><td>{n.open ?? '—'}</td><td>{n.high ?? '—'}</td><td>{n.low ?? '—'}</td><td>{n.close ?? '—'}</td><td>{n.ohlc_basis || '—'}</td><td>{n.source_url ? <a href={n.source_url} target="_blank" rel="noreferrer">{n.source_id || 'Source'}</a> : (n.source_id || '—')}</td></tr>)}
        </tbody></table></div> : <Empty>No NAV observations are stored for this fund.</Empty>}
      </Section>

      <Section id="snapshots" icon={Database} title={`Profile datasets (${profileData.length} snapshots)`} sub="Every source-published snapshot with its full payload, report date and provenance.">
        <div className="pf-dataset-bar">
          <select className="input pf-dataset-select" value={datasetFilter} onChange={(e) => setDatasetFilter(e.target.value)}>
            <option value="all">All datasets ({datasets.length})</option>
            {datasets.map((d) => <option key={d} value={d}>{d} ({grouped.get(d)?.length || 0})</option>)}
          </select>
          <span className="pf-hint">Showing {visibleDatasets.reduce((n, d) => n + (grouped.get(d)?.length || 0), 0)} snapshot(s)</span>
        </div>
        {visibleDatasets.length === 0 && <Empty>No profile snapshots are stored for this fund.</Empty>}
        <div className="pf-snapshot-groups">
          {visibleDatasets.map((d) => <div className="pf-snapshot-group" key={d}>
            <h3>{d.replaceAll('_', ' ')} <span>{grouped.get(d).length}</span></h3>
            {grouped.get(d).map((s) => <details className="pf-snapshot" key={s.id} open={grouped.get(d).length === 1}>
              <summary><span className="pf-snap-name">{d.replaceAll('_', ' ')}</span><span className="pf-snap-meta">{s.source_organization || s.source_id} · {s.source_report_date || `retrieved ${dt(s.retrieved_at)}`}</span><ChevronDown size={13} /></summary>
              <JsonBlock value={s.payload} maxHeight={340} />
              {s.source_url && <a className="pf-snap-source" href={s.source_url} target="_blank" rel="noreferrer"><ExternalLink size={11} /> View source document</a>}
            </details>)}
          </div>)}
        </div>
      </Section>

      {holdings.length > 0 && <Section id="holdings" icon={Layers} title={`Portfolio holdings (${holdings.length})`} sub="Filed positions with official N-PORT classification and metrics derived from consecutive SEC filings."
        action={reportDates.length > 1 ? <select className="input pf-report-select" value={reportDate} onChange={(e) => changeReportDate(e.target.value)}>{reportDates.map((d) => <option key={d} value={d}>{d}</option>)}</select> : null}>
        <div className="table-wrap pf-table pf-holdings"><table><thead><tr><th>SECURITY</th><th>TICKER</th><th>ISIN</th><th>CUSIP</th><th>WEIGHT %</th><th>QUANTITY</th><th>MARKET VALUE</th><th>ASSET CLASS</th><th>ISSUER TYPE</th><th>COUNTRY</th><th>SECTOR (SEC SIC)</th><th>FIRST REPORTED</th><th>SHARE CHG %</th><th>1Y PRICE RETURN</th><th>P/E (TRAILING)</th><th>SCOPE</th><th>SOURCE</th></tr></thead><tbody>
          {holdings.map((h) => <tr key={h.id}>
            <td className="pf-security">{h.security_name || '—'}</td>
            <td className="mono">{h.ticker || '—'}</td>
            <td className="mono">{h.isin || '—'}</td>
            <td className="mono">{h.cusip || '—'}</td>
            <td>{h.portfolio_weight == null ? '—' : `${Number(h.portfolio_weight).toFixed(2)}%`}</td>
            <td title={h.unit ? `${h.unit} · ${UNIT_LABELS[h.unit] || 'filed unit'}` : ''}>{h.quantity ?? '—'}</td>
            <td>{h.market_value != null ? money(h.market_value, h.currency || 'USD') : '—'}</td>
            <td title={h.asset_category ? `N-PORT asset category ${h.asset_category}` : ''}>{ASSET_CLASS_LABELS[h.asset_category] || h.asset_category || '—'}</td>
            <td title={h.issuer_type ? `N-PORT issuer type ${h.issuer_type}` : ''}>{ISSUER_TYPE_LABELS[h.issuer_type] || h.issuer_type || '—'}</td>
            <td>{h.investment_country || '—'}</td>
            <td title={h.sector_code ? `SEC SIC ${h.sector_code}${h.sector_description ? ` — ${h.sector_description}` : ''}` : 'No SEC SIC match for the filed ticker'}>{h.sector || '—'}</td>
            <td className="mono" title={h.metrics_calculation_basis || ''}>{h.first_bought_date ? String(h.first_bought_date).slice(0, 10) : '—'}</td>
            <td title={h.metrics_calculation_basis || ''}>{h.share_change_percentage == null && String(h.first_bought_date || '').slice(0, 10) === String(h.reporting_date || '').slice(0, 10) ? 'New' : signedPct(h.share_change_percentage)}</td>
            <td title={h.metrics_calculation_basis || ''}>{signedPct(h.one_year_return)}</td>
            <td title={h.trailing_pe_basis || ''}>{peText(h.trailing_pe)}</td>
            <td>{h.data_scope || '—'}</td>
            <td>{h.source_url ? <a href={h.source_url} target="_blank" rel="noreferrer">{h.data_source || 'Source'}</a> : (h.data_source || '—')}</td>
          </tr>)}
        </tbody></table></div>
        <p className="pf-table-note">First reported is the earliest N-PORT period in the imported archive window (a lower bound). Share change compares the fund's previous N-PORT report; 1Y return is the change in filed market value per share/principal about 12 months apart, excludes distributions and is not split-adjusted. Sector is the issuer's SEC EDGAR SIC group. P/E is trailing: N-PORT filed market value per share divided by the issuer's SEC XBRL annual diluted EPS for the fiscal year shown in the tooltip. No official U.S. source publishes a forward P/E, so no forecast is shown.</p>
      </Section>}

      {mutual?.mutual_fund && <Section id="normalized" icon={FileText} title="Normalized publisher profile" sub="Twelve Data-compatible sections assembled from FundFlow's own source-backed snapshots; no Twelve Data values are imported.">
        <div className="pf-normalized">
          {[...Object.entries(mutual.mutual_fund), ...(mutual._fundflow?.missing_sections || []).map((s) => [s, null])].map(([key, val]) => <div className="pf-norm-card" key={key}><div className="pf-norm-head"><b>{key.replaceAll('_', ' ')}</b>{!val && <span className="pf-na">unavailable</span>}</div>{val ? <JsonBlock value={val} maxHeight={220} /> : <small className="pf-na">Not published by the fund's official source.</small>}</div>)}
        </div>
      </Section>}

      {completeness && <Section id="completeness" icon={ShieldCheck} title="Data completeness" sub="Per-field and per-dataset availability; a present value is not a completeness claim.">
        <div className="pf-completeness">
          <div><h3>Fields</h3><div className="table-wrap pf-table"><table><thead><tr><th>FIELD</th><th>STATUS</th><th>VALUE</th></tr></thead><tbody>{completeness.fields.map((f) => <tr key={f.field}><td>{f.field.replaceAll('_', ' ')}</td><td><Status value={f.status} /></td><td>{f.value != null ? String(f.value) : <span className="pf-na">—</span>}</td></tr>)}</tbody></table></div></div>
          <div><h3>Datasets</h3><div className="table-wrap pf-table"><table><thead><tr><th>DATASET</th><th>STATUS</th><th>RECORDS</th><th>LATEST</th></tr></thead><tbody>{completeness.datasets.map((d) => <tr key={d.dataset}><td>{d.dataset.replaceAll('_', ' ')}</td><td><Status value={d.status} /></td><td>{d.records}</td><td className="mono">{d.latestReportDate || '—'}</td></tr>)}</tbody></table></div></div>
        </div>
      </Section>}

      <div className="pf-footer-note"><Info size={13} /> FundFlow shows only source-backed values; unavailable official fields remain empty rather than being filled from unofficial feeds.</div>
    </>}
  </div>;
}
