import React from 'react';

const ICONS = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  projects: <path d="M3 7V5h7l2 2h9v13H3V7Z" />,
  requirements: <><path d="M6 3h9l4 4v14H6Z" /><path d="M9 11h7M9 15h7M9 7h3" /></>,
  reviews: <><path d="M8 4h12v17H4V4h4M8 3h8v4H8Z" /><path d="m8 14 3 3 6-7" /></>,
  team: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M18 15a5 5 0 0 1 3 4v2" /></>,
  invitations: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 6 9 7 9-7" /></>,
  traceability: <><path d="m9 15 6-6M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 8l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" /></>,
  reports: <><path d="M4 3v18h17M8 16v-5M13 16V6M18 16v-8" /></>,
  activity: <path d="M2 12h5l3-8 4 16 3-8h5" />,
  settings: <><circle cx="12" cy="12" r="4" /><path d="m12 2 2 3 4-1 2 3-1 4 3 1-3 2 1 4-3 2-4-1-1 3-2-3-4 1-2-3 1-4-3-1 3-2-1-4 3-2 4 1Z" /></>,
  logout: <><path d="M10 3H4v18h6M9 12h13m-4-4 4 4-4 4" /></>,
  search: <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></>,
  bell: <><path d="M5 17h14l-2-4V8a5 5 0 0 0-10 0v5ZM10 21h4" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  plus: <path d="M12 4v16M4 12h16" />,
  alert: <><path d="m12 3 10 18H2Z" /><path d="M12 9v5m0 3v1" /></>,
  check: <path d="m4 12 5 5L20 6" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>,
};

export function Icon({ name, size = 20 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONS[name] || ICONS.dashboard}</svg>;
}

export function Badge({ value, risk = false }) {
  const label = value || (risk ? 'Unscored' : 'Not Reviewed');
  return <span className={`qm-badge qm-${label.toLowerCase().replaceAll(' ', '-')}`}>{label === 'Pending' ? 'Not Reviewed' : label}</span>;
}

export function formatDate(value) {
  if (!value) return 'Not recorded';
  const normalized = /(?:Z|[+-]\d{2}(?::?\d{2})?)$/i.test(value) ? value.replace(' ', 'T') : `${value.replace(' ', 'T')}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function Panel({ title, subtitle, action, children, className = '' }) {
  return <section className={`qm-panel ${className}`}><div className="qm-panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}

export function Empty({ children }) {
  return <p className="qm-empty">{children}</p>;
}

export function Distribution({ items, total, onSelect, risk = false }) {
  return <div className="qm-distribution">{items.map((item) => <button className="qm-distribution-row" key={item.value} onClick={() => onSelect(item.value)} aria-label={`${item.label}: ${item.count}, ${item.percent}%`}>
    <span className="qm-distribution-label"><Badge value={item.label} risk={risk} /><span><strong>{item.count}</strong><small>{item.percent}%</small></span></span>
    <span className="qm-track"><span className={`qm-fill qm-fill-${item.value.toLowerCase().replaceAll(' ', '-')}`} style={{ width: `${item.percent}%` }} /></span>
  </button>)}{!total && <Empty>No requirements match these filters.</Empty>}</div>;
}

export function RequirementTable({ rows, onAssign, pending = false }) {
  if (!rows.length) return <Empty>{pending ? 'No pending reviews.' : 'No requirements match this view.'}</Empty>;
  return <div className="qm-table-scroll"><table className="qm-table"><thead><tr><th>Requirement</th><th>Project / Type</th>{pending && <th>Submitted by</th>}<th>Risk</th><th>Review status</th><th>Assigned reviewer</th><th>{pending ? 'Submitted' : 'Updated'}</th><th>Action</th></tr></thead><tbody>
    {rows.map((row) => <tr key={row.id}>
      <td><a className="qm-row-title" href={`#admin/requirement/${row.id}`}><small>REQ-{row.id}</small>{row.title}</a>{row.attention_reasons?.length > 0 && <span className="qm-reason">{row.attention_reasons.join(' · ')}</span>}</td>
      <td><span>{row.project}</span><small>{row.requirement_type}</small></td>
      {pending && <td>{row.submitted_by || 'Not recorded'}</td>}
      <td><Badge value={row.risk_level} risk /></td><td><Badge value={row.review_status} /></td>
      <td>{row.assigned_reviewer || <span className="qm-unassigned">Unassigned</span>}</td><td className="qm-date">{formatDate(pending ? row.created_at : row.updated_at || row.created_at)}</td>
      <td><div className="qm-row-actions"><a href={`#admin/requirement/${row.id}`}>{pending ? 'View Details' : 'View Requirement'}</a><button onClick={() => onAssign(row)}>{row.assigned_reviewer_user_id ? 'Reassign Reviewer' : 'Assign Reviewer'}</button>{!pending && <a href={`#admin/requirement/${row.id}?review=1`}>Open Review</a>}</div></td>
    </tr>)}
  </tbody></table></div>;
}

export function ActivityList({ items }) {
  if (!items.length) return <Empty>No activity recorded yet. New requirement, review, invitation and management actions will appear here.</Empty>;
  return <ol className="qm-activity-list">{items.map((event) => <li key={event.id}><span className="qm-activity-icon"><Icon name={event.entity_type === 'requirement' ? 'reviews' : event.entity_type === 'invitation' ? 'invitations' : 'team'} size={17} /></span><div><p><strong>{event.actor_name}</strong> <span>{event.summary}</span></p><small>{event.entity_type === 'requirement' ? <a href={`#admin/requirement/${event.entity_id}`}>REQ-{event.entity_id}</a> : <span>{event.entity_type} {event.entity_id}</span>} · {formatDate(event.created_at)} · {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small></div></li>)}</ol>;
}
