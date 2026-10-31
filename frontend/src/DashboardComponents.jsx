import React from 'react';
import { CircleHelp } from 'lucide-react';
import { statusClass, statusLabel } from './dashboardFormat.js';

function PageTitle({ eyebrow, title, desc, actions }) { return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{desc}</p></div>{actions && <div className="title-actions">{actions}</div>}</div>; }
function Metric({ label, value, note, icon: Icon, tone = '' }) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={17}/></span></div><div className="metric-value">{value ?? '—'}</div><div className="metric-note">{note}</div></div>; }
function Status({ value }) { return <span className={`status ${statusClass(value)}`}><i/>{statusLabel(value)}</span>; }
function SectionHeading({ title, sub, action }) { return <div className="section-heading"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{action}</div>; }
function Empty({ children = 'No records yet.' }) { return <div className="empty"><CircleHelp size={18}/><span>{children}</span></div>; }
export { Empty, Metric, PageTitle, SectionHeading, Status };
