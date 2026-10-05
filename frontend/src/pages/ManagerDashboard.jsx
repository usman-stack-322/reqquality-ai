import React, { useEffect, useRef, useState } from 'react';
import Admin from './Admin';
import RequirementDetails from './RequirementDetails';
import { ActivityList, Badge, Distribution, Empty, Icon, Panel, RequirementTable } from '../components/ManagerUI';
import '../manager.css';

const NAV = [['dashboard', 'Dashboard'], ['projects', 'Projects'], ['requirements', 'Requirements'], ['reviews', 'Reviews'], ['team', 'Team Management'], ['invitations', 'Invitations'], ['traceability', 'Traceability'], ['reports', 'Reports'], ['activity', 'Activity Logs'], ['settings', 'Settings']];
const FILTER_KEYS = ['project', 'type', 'risk', 'review', 'reviewer', 'from', 'to', 'q', 'quality', 'page'];
const QUALITY = [['ambiguity', 'Ambiguity issues'], ['missing_information', 'Missing information'], ['testability', 'Testability issues'], ['conflicts', 'Conflict / inconsistency issues'], ['missing_criteria', 'Missing acceptance criteria'], ['missing_tests', 'Missing test scenarios'], ['high_risk', 'High / critical risk'], ['refinement', 'Needs refinement']];

function readRoute() {
  const [path, query = ''] = window.location.hash.slice(1).split('?');
  const detail = path.match(/^(?:admin\/)?requirement\/(\d+)$/);
  const section = detail ? 'detail' : path.startsWith('admin/') ? path.slice(6) : 'dashboard';
  return { section: NAV.some(([key]) => key === section) || section === 'detail' ? section : 'dashboard', id: detail ? Number(detail[1]) : null, query };
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'include', ...options });
  let data;
  try { data = await response.json(); } catch { throw new Error('The server returned an invalid response. Please try again.'); }
  if (!response.ok) throw new Error(data.error || 'Unable to complete this request.');
  return data;
}

function Filters({ values, reviewers, onChange, onReset }) {
  const select = (name, label, options) => <label>{label}<select value={values.get(name) || ''} onChange={(event) => onChange(name, event.target.value)}>{options.map(([value, text]) => <option value={value} key={value}>{text}</option>)}</select></label>;
  return <section className="qm-filters" aria-label="Dashboard filters">
    {select('project', 'Project', [['', 'All projects'], ['current', 'ReqQuality AI']])}
    {select('type', 'Requirement type', [['', 'All types'], ...['Functional', 'Non-Functional', 'Business'].map((value) => [value, value])])}
    {select('risk', 'Risk level', [['', 'All risk levels'], ['high-critical', 'High / Critical'], ...['Low', 'Medium', 'High', 'Critical'].map((value) => [value, value]), ['unscored', 'Unscored']])}
    {select('review', 'Review status', [['', 'All statuses'], ['pending-reviews', 'Pending reviews'], ['Pending', 'Not Reviewed'], ['In Review', 'In Review'], ['Approved', 'Approved'], ['Needs Revision', 'Needs Revision']])}
    {select('reviewer', 'Reviewer', [['', 'All reviewers'], ['unassigned', 'Unassigned'], ...reviewers.map((member) => [String(member.id), member.name])])}
    <label>Created from<input type="date" value={values.get('from') || ''} onChange={(event) => onChange('from', event.target.value)} /></label>
    <label>Created to<input type="date" value={values.get('to') || ''} onChange={(event) => onChange('to', event.target.value)} /></label>
    <button className="qm-reset" onClick={onReset}>Reset</button>
  </section>;
}

function AssignmentDialog({ row, reviewers, csrfToken, onClose, onSaved }) {
  const dialog = useRef(null);
  const [reviewer, setReviewer] = useState(row.assigned_reviewer_user_id || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { dialog.current.showModal(); }, []);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await api(`/api/admin/requirements/${row.id}/reviewer`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, body: JSON.stringify({ reviewer_id: reviewer ? Number(reviewer) : null }) });
      onSaved('Reviewer assignment saved.'); onClose();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <dialog ref={dialog} className="qm-dialog" onCancel={(event) => { if (busy) event.preventDefault(); else onClose(); }} aria-labelledby="assignment-title"><form onSubmit={save}><p className="eyebrow">REQ-{row.id}</p><h2 id="assignment-title">Assign a reviewer</h2><p>{row.title}</p><label>SQA Engineer<select value={reviewer} onChange={(event) => setReviewer(event.target.value)} disabled={busy}><option value="">Unassigned</option>{reviewers.filter((member) => member.status === 'Active').map((member) => <option key={member.id} value={member.id}>{member.name} · {member.workload} open reviews</option>)}</select></label>{!reviewers.some((member) => member.status === 'Active') && <p>No active SQA Engineers. Invite an engineer from Team Management.</p>}{error && <p className="error" role="alert">{error}</p>}<div className="qm-dialog-actions"><button className="qm-secondary" type="button" onClick={onClose} disabled={busy}>Cancel</button><button disabled={busy}>{busy ? 'Saving...' : 'Save assignment'}</button></div></form></dialog>;
}

function TeamTable({ members, onChange, busy }) {
  if (!members.length) return <Empty>No team members have joined yet.</Empty>;
  return <div className="qm-table-scroll"><table className="qm-table"><thead><tr><th>Team member</th><th>Role</th><th>Status</th><th>Open assignments</th><th>Manage access</th></tr></thead><tbody>{members.map((member) => <tr key={member.id}><td><strong>{member.name}</strong><small>{member.email}</small></td><td>{member.role === 'admin' ? 'QA Manager' : <select aria-label={`Role for ${member.name}`} value={member.role} disabled={busy || !onChange} onChange={(event) => onChange(member.id, { role: event.target.value })}><option>Analyst</option><option>SQA Engineer</option></select>}</td><td><Badge value={member.status} /></td><td>{member.workload}</td><td>{member.role === 'admin' ? <small>Organization administrator</small> : onChange ? <button className="qm-secondary" disabled={busy} onClick={() => onChange(member.id, { is_active: member.status !== 'Active' })}>{member.status === 'Active' ? 'Disable account' : 'Enable account'}</button> : <a href="#admin/team">Manage</a>}</td></tr>)}</tbody></table></div>;
}

function Workload({ members, onSelect }) {
  return <Panel title="Reviewer Workload" subtitle="Open assignments and completed reviews · no performance ranking">
    {!members.length ? <Empty>No SQA Engineers have joined yet.</Empty> : <div className="qm-table-scroll"><table className="qm-table"><thead><tr><th>SQA Engineer</th><th>Assigned</th><th>Pending</th><th>Completed</th><th>High-risk open</th></tr></thead><tbody>{members.map((member) => <tr key={member.id}><td><button className="qm-text-button" onClick={() => onSelect(member.id)}>{member.name}</button>{member.status === 'Disabled' && <small>Disabled</small>}</td><td>{member.assigned}</td><td>{member.pending}</td><td>{member.completed}</td><td>{member.high_risk}</td></tr>)}</tbody></table></div>}
  </Panel>;
}

function Settings({ organization, user, csrfToken, onSaved, onSignedOut, tab }) {
  const [name, setName] = useState(organization.name);
  const [days, setDays] = useState(organization.overdue_days);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(event, password = false) {
    event.preventDefault(); setError('');
    if (password && newPassword !== confirm) { setError('Passwords must match.'); return; }
    setBusy(true);
    try {
      const result = await api(password ? '/api/auth/change-password' : '/api/admin/settings', { method: password ? 'POST' : 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, body: JSON.stringify(password ? { current_password: currentPassword, new_password: newPassword } : { name, overdue_days: Number(days) }) });
      if (password) onSignedOut(result.message); else onSaved(result.message);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="qm-settings-grid">{error && <p className="error" role="alert">{error}</p>}
    <Panel title="My Profile" subtitle="Your organization administrator account"><div className="qm-profile-details"><span className="qm-avatar large">{user.name.slice(0, 2).toUpperCase()}</span><h3>{user.name}</h3><p>{user.email}</p><Badge value="QA Manager" /></div></Panel>
    {tab !== 'password' && <Panel title="Organization Settings" subtitle="Used in this workspace and its review attention queue"><form className="qm-settings-form" onSubmit={(event) => save(event)}><label>Organization / company name<input required minLength={2} maxLength={100} value={name} onChange={(event) => setName(event.target.value)} /></label><label>Flag pending reviews after (days)<input type="number" required min={1} max={90} value={days} onChange={(event) => setDays(event.target.value)} /></label><button disabled={busy}>Save settings</button></form></Panel>}
    {tab !== 'profile' && <Panel title="Change Password" subtitle="Changing your password signs out all existing sessions"><form className="qm-settings-form" onSubmit={(event) => save(event, true)}><label>Current password<input type="password" autoComplete="current-password" required maxLength={128} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label><label>New password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label><label>Confirm new password<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label><button disabled={busy}>Update password</button></form></Panel>}
  </div>;
}

export default function ManagerDashboard({ user, csrfToken, onLogout, logoutError, onSignedOut }) {
  const [route, setRoute] = useState(readRoute);
  const [data, setData] = useState(null);
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
  const [assignment, setAssignment] = useState(null);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [search, setSearch] = useState('');
  useEffect(() => {
    const update = () => { setRoute(readRoute()); setMenu(false); setNotifications(false); setSidebar(false); setNotice(''); };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  const params = new URLSearchParams(route.query);
  const filters = new URLSearchParams();
  if (route.section !== 'detail') FILTER_KEYS.forEach((key) => { if (params.get(key)) filters.set(key, params.get(key)); });
  if (route.section === 'reviews' && !filters.has('review')) filters.set('review', 'pending-reviews');
  const query = filters.toString();
  const showList = ['requirements', 'reviews'].includes(route.section);
  useEffect(() => { setSearch(new URLSearchParams(query).get('q') || ''); }, [query]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    const options = { signal: controller.signal };
    Promise.all([api(`/api/admin/dashboard?${query}`, options), showList ? api(`/api/admin/requirements?${query}`, options) : Promise.resolve(null)])
      .then(([dashboard, rows]) => { if (!controller.signal.aborted) { setData(dashboard); setListing(rows); } })
      .catch((err) => { if (err.name !== 'AbortError') setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [query, showList, revision, route.section]);
  function navigate(section, changes = {}, retain = true) {
    const next = new URLSearchParams(retain ? query : '');
    next.delete('page');
    Object.entries(changes).forEach(([key, value]) => { if (value === '' || value === null) next.delete(key); else next.set(key, String(value)); });
    window.location.hash = `admin${section === 'dashboard' ? '' : `/${section}`}${next.size ? `?${next}` : ''}`;
  }
  function saved(message) { setNotice(message); setRevision((value) => value + 1); }
  async function changeMember(id, change) {
    setBusy(true); setError('');
    try {
      const result = await api(`/api/admin/users/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, body: JSON.stringify(change) });
      saved(result.message);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  const reviewers = data?.team.filter((member) => member.role === 'SQA Engineer') || [];
  const title = route.section === 'dashboard' ? 'QA Manager Dashboard' : route.section === 'detail' ? `Requirement REQ-${route.id}` : NAV.find(([key]) => key === route.section)?.[1];
  const filterVisible = ['dashboard', 'requirements', 'reviews', 'traceability', 'projects'].includes(route.section);
  const link = (label, section, changes) => <button className="qm-text-button" onClick={() => navigate(section, changes)}>{label} <Icon name="arrow" size={15} /></button>;
  const invite = () => navigate('invitations', { invite: 1 }, false);
  const trace = data?.traceability;

  return <div className="qm-shell">
    <aside className={`qm-sidebar ${sidebar ? 'is-open' : ''}`} aria-label="QA Manager navigation"><a className="qm-brand" href="#admin"><span className="qm-brand-mark">RQ</span><span>ReqQuality <b>AI</b><small>QUALITY WORKSPACE</small></span></a><div className="qm-workspace"><span className="qm-workspace-symbol">Q</span><div><strong>{data?.organization.name || 'Organization'}</strong><small>QA Manager workspace</small></div></div><p className="qm-nav-label">WORKSPACE</p><nav>{NAV.map(([key, label]) => <a key={key} href={`#admin${key === 'dashboard' ? '' : `/${key}`}`} className={route.section === key || (route.section === 'detail' && key === 'requirements') ? 'active' : ''} aria-current={route.section === key ? 'page' : undefined}><Icon name={key} /><span>{label}</span>{key === 'reviews' && data?.summary.pending_reviews > 0 && <span className="qm-nav-count">{data.summary.pending_reviews}</span>}</a>)}</nav><div className="qm-sidebar-bottom"><span className="qm-access-tag"><Icon name="check" size={15} /> Organization administrator</span><button onClick={onLogout}><Icon name="logout" /> Logout</button><small>ReqQuality AI · Quality with clarity</small></div></aside>
    <div className="qm-main"><header className="qm-topbar"><button className="qm-mobile-toggle" onClick={() => setSidebar(!sidebar)} aria-expanded={sidebar} aria-label="Toggle navigation"><Icon name="dashboard" /></button><div className="qm-top-title"><span>{data?.organization.name || 'ReqQuality AI'} <span className="qm-slash">/</span> Quality management</span><h1>{title}</h1></div><form className="qm-search" onSubmit={(event) => { event.preventDefault(); navigate('requirements', { q: search }, false); }}><Icon name="search" size={18} /><input aria-label="Search requirements" placeholder="Search requirements..." maxLength={200} value={search} onChange={(event) => setSearch(event.target.value)} /><button type="submit" aria-label="Run search"><Icon name="arrow" size={16} /></button></form><div className="qm-top-actions"><button className="qm-icon-button" aria-label="Review notifications" aria-expanded={notifications} onClick={() => { setNotifications(!notifications); setMenu(false); }}><Icon name="bell" />{data?.attention_total > 0 && <span className="qm-notification-dot" />}</button><button className="qm-profile-button" onClick={() => { setMenu(!menu); setNotifications(false); }} aria-expanded={menu} aria-label="Open profile menu"><span className="qm-avatar">{user.name.slice(0, 2).toUpperCase()}</span><span><strong>{user.name}</strong><small>QA Manager</small></span><span aria-hidden="true">⌄</span></button>
      {menu && <div className="qm-dropdown"><a href="#admin/settings?tab=profile">My Profile</a><a href="#admin/settings">Organization Settings</a><a href="#admin/settings?tab=password">Change Password</a><button onClick={onLogout}>Logout</button></div>}
      {notifications && <div className="qm-dropdown qm-notifications"><strong>Review attention</strong><p>{data?.summary.pending_reviews || 0} pending reviews · {data?.summary.overdue || 0} overdue</p>{link('Open attention queue', 'requirements', { quality: 'attention' })}</div>}
    </div></header>

    <main className="qm-content">
      {(error || logoutError) && <div className="qm-error" role="alert">{error || logoutError} <button onClick={() => setRevision((value) => value + 1)}>Retry</button></div>}
      {notice && <p className="qm-notice" role="status">{notice}</p>}
      {filterVisible && <Filters values={filters} reviewers={reviewers} onChange={(key, value) => navigate(route.section, { [key]: value })} onReset={() => navigate(route.section, {}, false)} />}
      {filterVisible && (filters.get('q') || filters.get('quality')) && <div className="qm-applied">{filters.get('q') && <span>Search: {filters.get('q')}</span>}{filters.get('quality') && <span>Quality: {QUALITY.find(([key]) => key === filters.get('quality'))?.[1] || filters.get('quality').replaceAll('_', ' ')}</span>}<button onClick={() => navigate(route.section, { q: '', quality: '' })}>Clear</button></div>}
      {loading && <p className="qm-loading" role="status">Loading quality workspace...</p>}
      {!loading && !data && <Empty>Dashboard data is unavailable. Use Retry to reconnect.</Empty>}
      {data && !error && <>
        {filterVisible && <p className="qm-scope">{data.scope_note}</p>}
        {route.section === 'dashboard' && <>
          <div className="qm-page-intro"><div><p className="qm-eyebrow">ORGANIZATION OVERVIEW</p><h2>Quality at a glance</h2><p>Keep reviews moving. Focus your team where quality needs attention.</p></div><div className="qm-intro-actions"><button className="qm-secondary" onClick={() => setRevision((value) => value + 1)}>Refresh</button><button onClick={invite}><Icon name="plus" size={17} /> Invite User</button></div></div>
          <section className="qm-kpis" aria-label="Key quality metrics">{[
            ['Total Requirements', data.summary.total, `${data.summary.analyzed} analyzed`, 'requirements', {}, 'requirements', ''],
            ['Pending Reviews', data.summary.pending_reviews, `${data.summary.unassigned} unassigned · ${data.summary.overdue} overdue`, 'reviews', { review: 'pending-reviews' }, 'clock', 'attention'],
            ['Approved Requirements', data.summary.approved, 'SQA-approved and ready', 'requirements', { review: 'Approved' }, 'check', 'approved'],
            ['High / Critical Risk', data.summary.high_risk, 'Prioritize for quality review', 'requirements', { risk: 'high-critical' }, 'alert', 'risk'],
          ].map(([label, value, detail, section, changes, icon, tone]) => <button className={`qm-kpi ${tone}`} key={label} onClick={() => navigate(section, changes)}><span className="qm-kpi-top">{label}<span><Icon name={icon} size={20} /></span></span><strong>{value}</strong><span className="qm-kpi-detail">{detail}<Icon name="arrow" size={16} /></span></button>)}</section>
          <section className="qm-quick-actions" aria-label="Quick actions"><strong>Quick actions</strong><button onClick={invite}><Icon name="plus" size={16} /> Invite Team Member</button><button onClick={() => navigate('reviews', { review: 'pending-reviews' })}>View Pending Reviews</button><button onClick={() => navigate('requirements', { risk: 'high-critical' })}>View High-Risk Requirements</button><a href="#admin/team">Manage Team</a><a href="#admin/reports">Open Reports <Icon name="arrow" size={14} /></a></section>
          <div className="qm-charts-grid"><Panel title="Requirement Review Status" subtitle="Current review decisions across matching requirements"><Distribution items={data.review_distribution} total={data.summary.total} onSelect={(value) => navigate('requirements', { review: value })} /><p className="qm-footnote">Requirements awaiting their first review appear as Not Reviewed. Rework is tracked as Needs Revision.</p></Panel><Panel title="Risk Distribution" subtitle="Requirement quality risk from saved analysis"><Distribution items={data.risk_distribution} total={data.summary.total} risk onSelect={(value) => navigate('requirements', { risk: value })} /><p className="qm-footnote">{data.unscored} unscored · percentages include all matching requirements.</p></Panel><Panel title="Traceability Overview" subtitle="Acceptance criteria + test scenarios"><div className="qm-coverage-ring" style={{ '--coverage': `${trace.coverage}%` }}><div><strong>{trace.coverage}%</strong><span>Coverage</span></div></div><div className="qm-mini-stats"><span>Acceptance criteria<strong>{trace.with_criteria}</strong></span><span>Test scenarios<strong>{trace.with_tests}</strong></span><span>Reviewed by SQA<strong>{trace.reviewed}</strong></span><span>Missing links<strong>{trace.missing_links}</strong></span></div>{link('Explore traceability', 'traceability', {})}</Panel></div>
          <Panel title="Requirements Needing Attention" subtitle={`${data.attention_total} requirements need attention · showing up to 8`} action={link('View All', 'requirements', { quality: 'attention' })}><RequirementTable rows={data.attention} onAssign={setAssignment} /></Panel>
          <Panel title="Pending SQA Reviews" subtitle="Unassigned reviews first, then oldest submissions" action={link('View All', 'reviews', { review: 'pending-reviews' })}><RequirementTable rows={data.pending_reviews} pending onAssign={setAssignment} /></Panel>
          <div className="qm-two-columns"><Panel title="Requirement Quality Overview" subtitle="Click a finding to inspect matching requirements"><div className="qm-quality-list">{QUALITY.map(([key, label]) => <button key={key} disabled={key === 'conflicts' && !data.conflicts_available} onClick={() => navigate('requirements', { quality: key })}><span>{label}</span><strong>{key === 'conflicts' && !data.conflicts_available ? 'Not assessed' : data.quality[key]}</strong><Icon name="arrow" size={15} /></button>)}</div></Panel><Panel title="Quality Trends" subtitle="Current risk by requirement creation month"><div className="qm-trends">{!data.trends.length ? <Empty>No analyzed requirement cohorts yet.</Empty> : data.trends.map((point) => <div className="qm-trend-row" key={point.month}><span>{point.month}</span><div><div className="qm-track"><span style={{ width: `${point.average_risk || 0}%` }} /></div><small>{point.count} requirements · {point.approved} currently approved</small></div><strong>{point.average_risk ?? '—'}<small>/100 risk</small></strong></div>)}</div><p className="qm-footnote">Higher risk needs more refinement. These are creation cohorts using current scores, not historical score snapshots.</p></Panel></div>
          <Workload members={data.reviewer_workload} onSelect={(id) => navigate('requirements', { reviewer: id })} />
          <div className="qm-two-columns"><Panel title="Team Overview" subtitle="People and current review capacity" action={<a href="#admin/team">Manage Team <Icon name="arrow" size={15} /></a>}><div className="qm-team-stats"><span><strong>{data.team_summary.total}</strong>Members</span><span><strong>{data.team_summary.analysts}</strong>Analysts</span><span><strong>{data.team_summary.engineers}</strong>SQA Engineers</span><span><strong>{data.team_summary.active}</strong>Active</span></div><ul className="qm-member-list">{data.team.slice(0, 5).map((member) => <li key={member.id}><span className="qm-avatar">{member.name.slice(0, 2).toUpperCase()}</span><div><strong>{member.name}</strong><small>{member.email}</small></div><span><small>{member.role === 'admin' ? 'QA Manager' : member.role}</small><small>{member.status} · {member.workload} open</small></span></li>)}</ul><div className="qm-invitation-summary">{Object.entries(data.invitations).map(([status, count]) => <a href="#admin/invitations" key={status}><strong>{count}</strong><span>{status} invitations</span></a>)}</div><button className="qm-secondary" onClick={invite}>+ Invite User</button></Panel><Panel title="Recent Activity" subtitle="Recorded team actions" action={<a href="#admin/activity">View All <Icon name="arrow" size={15} /></a>}><ActivityList items={data.activity.slice(0, 6)} /></Panel></div>
        </>}

        {showList && <Panel title={route.section === 'reviews' ? 'SQA Review Queue' : 'Requirements'} subtitle={`${listing?.total || 0} matching requirements`}><RequirementTable rows={listing?.requirements || []} pending={route.section === 'reviews'} onAssign={setAssignment} /><div className="qm-pagination"><button className="qm-secondary" disabled={!listing || listing.page <= 1} onClick={() => navigate(route.section, { page: listing.page - 1 })}>Previous</button><span>Page {listing?.page || 1} of {Math.max(1, Math.ceil((listing?.total || 0) / (listing?.page_size || 20)))}</span><button className="qm-secondary" disabled={!listing || listing.page * listing.page_size >= listing.total} onClick={() => navigate(route.section, { page: listing.page + 1 })}>Next</button></div></Panel>}
        {route.section === 'detail' && <><p className="qm-scope">QA Managers inspect and assign reviews. SQA Engineers record review decisions.</p><RequirementDetails requirementId={route.id} user={user} csrfToken={csrfToken} managerView revision={revision} onAssign={setAssignment} openReview={params.get('review') === '1'} /></>}
        {route.section === 'team' && <><div className="qm-page-intro"><div><h2>Your quality team</h2><p>Manage access and supported roles. Disabled or reassigned users lose their existing sessions; ineligible reviewers' open assignments are cleared.</p></div><button onClick={invite}><Icon name="plus" size={17} /> Invite Team Member</button></div><Panel title="Registered members" subtitle={`${data.team_summary.active} active of ${data.team_summary.total} members`}><TeamTable members={data.team} onChange={changeMember} busy={busy} /></Panel><Panel title="Invited members" subtitle="Valid pending invitations">{!data.invited_members.length ? <Empty>No pending invitations.</Empty> : <ul className="qm-member-list">{data.invited_members.map((member) => <li key={member.id}><div><strong>{member.name}</strong><small>{member.email}</small></div><span>{member.role}</span><Badge value="Invited" /><a href="#admin/invitations">Manage invitation</a></li>)}</ul>}</Panel><Workload members={data.reviewer_workload} onSelect={(id) => navigate('requirements', { reviewer: id }, false)} /></>}
        {route.section === 'invitations' && <Admin csrfToken={csrfToken} initialInvite={params.get('invite') === '1'} onChanged={() => setRevision((value) => value + 1)} />}
        {route.section === 'traceability' && <Panel title="Traceability Overview" subtitle="Coverage = requirements with at least one acceptance criterion AND one test scenario / all matching requirements"><div className="qm-trace-cards">{[['With acceptance criteria', trace.with_criteria, 'has_criteria'], ['With test scenarios', trace.with_tests, 'has_tests'], ['Reviewed by SQA', trace.reviewed, 'reviewed'], ['Fully traceable', trace.fully_traceable, 'traceable'], ['Missing traceability links', trace.missing_links, 'traceability_gaps']].map(([label, count, quality]) => <button key={label} onClick={() => navigate('requirements', { quality })}><strong>{count}</strong><span>{label}</span></button>)}</div><div className="qm-track qm-trace-track"><span style={{ width: `${trace.coverage}%` }} /></div><p>{trace.coverage}% coverage. Reviewed by SQA is reported separately and is not required by the existing coverage formula.</p><button onClick={() => navigate('requirements', { quality: 'traceability_gaps' })}>Inspect missing links</button></Panel>}
        {route.section === 'projects' && <Panel title="Project Overview" subtitle="This installation currently stores one shared project"><div className="qm-project-card"><span className="qm-project-icon"><Icon name="projects" size={28} /></span><div><h3>ReqQuality AI</h3><p>{data.summary.total} requirements · {data.summary.analyzed} analyzed</p></div><div className="qm-project-stats"><span><strong>{data.summary.pending_reviews}</strong>Pending</span><span><strong>{data.summary.approved}</strong>Approved</span><span><strong>{data.summary.high_risk}</strong>High risk</span></div><button onClick={() => navigate('requirements', { project: 'current' })}>Open project</button></div><div className="qm-track qm-trace-track"><span style={{ width: `${data.summary.total ? data.summary.approved * 100 / data.summary.total : 0}%` }} /></div><p className="qm-footnote">Review progress: {data.summary.total ? Math.round(data.summary.approved * 100 / data.summary.total) : 0}% approved. This workspace contains one shared project.</p></Panel>}
        {route.section === 'reports' && <Panel title="Quality Reports" subtitle="Exports include all requirements in the current shared project"><div className="qm-report-grid"><article><Icon name="reports" size={30} /><h3>Project quality report</h3><p>Review progress, risk, scenarios, and requirement traceability.</p><a className="button" href="/api/reports/project.pdf" download>Download PDF</a></article><article><Icon name="requirements" size={30} /><h3>Requirements register</h3><p>Export the existing requirement fields for further analysis.</p><a className="button" href="/api/exports/requirements.csv" download>Download CSV</a></article></div></Panel>}
        {route.section === 'activity' && <Panel title="Activity Logs" subtitle="Latest 50 recorded events · logging begins with this dashboard upgrade"><ActivityList items={data.activity} /></Panel>}
        {route.section === 'settings' && <Settings key={params.get('tab') || 'organization'} organization={data.organization} user={user} csrfToken={csrfToken} onSaved={saved} onSignedOut={onSignedOut} tab={params.get('tab')} />}
      </>}
      <footer className="qm-footer">ReqQuality AI <span>AI-Powered Requirements &amp; Software Quality Engineering</span></footer>
    </main></div>
    {assignment && <AssignmentDialog row={assignment} reviewers={reviewers} csrfToken={csrfToken} onClose={() => setAssignment(null)} onSaved={saved} />}
  </div>;
}
