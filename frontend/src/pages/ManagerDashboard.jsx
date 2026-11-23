import React, { useEffect, useRef, useState } from 'react';
import { Bell, ChevronDown, Plus, RefreshCw, Search, Shield } from 'lucide-react';
import { apiFetch as fetch } from '../api.js';
import QualityMetrics from '../components/QualityMetrics';
import DashboardCharts from '../components/DashboardCharts';
import ProjectContext from '../components/ProjectContext';
import Admin from './Admin';
import RequirementDetails from './RequirementDetails';
import LoadingSkeleton from '../components/LoadingSkeleton';
import PdfExportButton from '../components/PdfExportButton';
import WorkspaceShell, { ADMIN_NAV_ICONS } from '../components/WorkspaceShell';
import { ActivityList, Badge, Empty, Icon, Panel, RequirementTable } from '../components/ManagerUI';
import { PageHeader, buttonPrimaryClass, buttonSecondaryClass, inputClass } from '../components/ui';

const NAV = [
  ['dashboard', 'Dashboard'],
  ['projects', 'Projects'],
  ['requirements', 'Requirements'],
  ['reviews', 'Review Queue'],
  ['traceability', 'Traceability'],
  ['reports', 'Reports'],
  ['team', 'Team & Admin'],
  ['invitations', 'Invitations'],
  ['permissions', 'Role Permissions'],
  ['activity', 'Activity Logs'],
  ['settings', 'Settings'],
];
const FILTER_KEYS = ['project', 'type', 'risk', 'review', 'reviewer', 'from', 'to', 'q', 'quality', 'page'];
const QUALITY = [
  ['ambiguity', 'Ambiguity issues'],
  ['missing_information', 'Missing information'],
  ['testability', 'Testability issues'],
  ['conflicts', 'Conflict / inconsistency issues'],
  ['missing_criteria', 'Missing acceptance criteria'],
  ['missing_tests', 'Missing test scenarios'],
  ['high_risk', 'High / critical risk'],
  ['refinement', 'Needs refinement'],
];

function readRoute() {
  const [path, query = ''] = window.location.hash.slice(1).split('?');
  const detail = path.match(/^(?:admin\/)?requirement\/(\d+)$/);
  let section = detail ? 'detail' : path.startsWith('admin/') ? path.slice(6) : 'dashboard';
  if (path === 'projects') section = 'projects';
  if (path === 'review-queue') section = 'reviews';
  if (path === 'test-cases') section = 'traceability';
  if (path === 'reports') section = 'reports';
  if (path === 'bugs') section = 'dashboard';
  return {
    section: NAV.some(([key]) => key === section) || section === 'detail' ? section : 'dashboard',
    id: detail ? Number(detail[1]) : null,
    query,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'include', ...options });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('The server returned an invalid response. Please try again.');
  }
  if (!response.ok) throw new Error(data.error || 'Unable to complete this request.');
  return data;
}

function RolePermissions({ csrfToken }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api('/api/admin/roles')
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);

  async function save(role) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api(`/api/admin/roles/${encodeURIComponent(role)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(data.roles[role]),
      });
      setNotice(result.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Role Permissions" subtitle="Changes apply immediately to all users in the selected role. Admin access is fixed.">
      {error && <p className="mb-3 rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
      {notice && <p className="mb-3 rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">{notice}</p>}
      {!data && !error && <p className="text-xs text-muted" role="status">Loading permissions…</p>}
      {data && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {Object.entries(data.roles).map(([role, permissions]) => (
            <fieldset key={role} disabled={busy} className="rounded-xl border border-line bg-surface-alt/40 p-4 space-y-3">
              <legend className="px-1 text-sm font-semibold text-ink">{role}</legend>
              <div className="space-y-2">
                {data.permissions.map((permission) => (
                  <label key={permission} className="flex items-center gap-2 text-xs text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={permissions[permission]}
                      onChange={(event) =>
                        setData((previous) => ({
                          ...previous,
                          roles: { ...previous.roles, [role]: { ...previous.roles[role], [permission]: event.target.checked } },
                        }))
                      }
                    />
                    <span className="capitalize">{permission.replaceAll('_', ' ')}</span>
                  </label>
                ))}
              </div>
              <button type="button" className={buttonPrimaryClass} onClick={() => save(role)} disabled={busy}>
                Save {role} permissions
              </button>
            </fieldset>
          ))}
        </div>
      )}
    </Panel>
  );
}

function Filters({ values, reviewers, onChange, onReset }) {
  const select = (name, label, options) => (
    <label className="block space-y-1 text-xs font-medium text-muted">
      <span>{label}</span>
      <select className={inputClass} value={values.get(name) || ''} onChange={(event) => onChange(name, event.target.value)}>
        {options.map(([value, text]) => (
          <option value={value} key={value}>{text}</option>
        ))}
      </select>
    </label>
  );
  return (
    <section className="rounded-xl border border-line bg-surface p-4 shadow-xs" aria-label="Dashboard filters">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-8">
        {select('project', 'Project', [['', 'All projects'], ['current', 'ReqQuality AI']])}
        {select('type', 'Requirement type', [['', 'All types'], ...['Functional', 'Non-Functional', 'Business'].map((value) => [value, value])])}
        {select('risk', 'Risk level', [['', 'All risk levels'], ['high-critical', 'High / Critical'], ...['Low', 'Medium', 'High', 'Critical'].map((value) => [value, value]), ['unscored', 'Unscored']])}
        {select('review', 'Review status', [['', 'All statuses'], ['pending-reviews', 'Pending reviews'], ['Draft', 'Draft'], ['Ready for Review', 'Ready for Review'], ['Pending', 'Historical Pending'], ['In Review', 'In Review'], ['Approved', 'Approved'], ['Needs Revision', 'Needs Revision']])}
        {select('reviewer', 'Reviewer', [['', 'All reviewers'], ['unassigned', 'Unassigned'], ...reviewers.map((member) => [String(member.id), member.name])])}
        <label className="block space-y-1 text-xs font-medium text-muted">
          <span>Created from</span>
          <input className={inputClass} type="date" value={values.get('from') || ''} onChange={(event) => onChange('from', event.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-muted">
          <span>Created to</span>
          <input className={inputClass} type="date" value={values.get('to') || ''} onChange={(event) => onChange('to', event.target.value)} />
        </label>
        <div className="flex items-end">
          <button type="button" className={`${buttonSecondaryClass} w-full`} onClick={onReset}>Reset</button>
        </div>
      </div>
    </section>
  );
}

function AssignmentDialog({ row, reviewers, csrfToken, onClose, onSaved }) {
  const dialog = useRef(null);
  const [reviewer, setReviewer] = useState(row.assigned_reviewer_user_id || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api(`/api/admin/requirements/${row.id}/reviewer`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ reviewer_id: reviewer ? Number(reviewer) : null }),
      });
      onSaved('Reviewer assignment saved.');
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="m-auto w-[min(92vw,440px)] rounded-2xl border border-line bg-surface p-6 text-ink shadow-xl"
      onCancel={(event) => {
        if (busy) event.preventDefault();
        else onClose();
      }}
      aria-labelledby="assignment-title"
    >
      <form onSubmit={save} className="space-y-4">
        <div className="space-y-1">
          <p className="font-mono text-xs font-semibold text-accent">REQ-{row.id}</p>
          <h2 id="assignment-title" className="text-lg font-bold text-ink">Assign a reviewer</h2>
          <p className="text-xs text-muted">{row.title}</p>
        </div>
        <label className="block space-y-1.5 text-xs font-semibold text-ink">
          <span>SQA Engineer</span>
          <select className={inputClass} value={reviewer} onChange={(event) => setReviewer(event.target.value)} disabled={busy}>
            <option value="">Unassigned</option>
            {reviewers
              .filter((member) => member.status === 'Active')
              .map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name} · {member.workload} open reviews
                </option>
              ))}
          </select>
        </label>
        {!reviewers.some((member) => member.status === 'Active') && (
          <p className="text-xs text-warning">No active SQA Engineers. Invite an engineer from Team Management.</p>
        )}
        {error && <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className={buttonSecondaryClass} autoFocus onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className={buttonPrimaryClass} disabled={busy}>{busy ? 'Saving…' : 'Save assignment'}</button>
        </div>
      </form>
    </dialog>
  );
}

function TeamTable({ members, onChange, onProjectAccess, busy }) {
  if (!members.length) return <Empty>No team members have joined yet.</Empty>;
  return (
    <div className="table-wrapper" tabIndex={0} role="region" aria-label="Registered team members">
      <table className="min-w-[720px] text-left text-xs">
        <caption className="visually-hidden">Team members</caption>
        <thead>
          <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wider text-muted">
            <th scope="col" className="px-4 py-3">Team member</th>
            <th scope="col" className="px-4 py-3">Role</th>
            <th scope="col" className="px-4 py-3">Status</th>
            <th scope="col" className="px-4 py-3">Open assignments</th>
            <th scope="col" className="px-4 py-3 text-right">Manage access</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {members.map((member) => (
            <tr key={member.id} className="hover:bg-surface-alt/50">
              <td className="px-4 py-3">
                <strong className="block font-semibold text-ink">{member.name}</strong>
                <small className="text-[11px] text-muted">{member.email}</small>
              </td>
              <td className="px-4 py-3">
                {member.role === 'admin' ? (
                  <Badge value="SQA Admin" />
                ) : (
                  <select
                    aria-label={`Role for ${member.name}`}
                    className={`${inputClass} w-auto py-1 text-xs`}
                    value={member.role}
                    disabled={busy || !onChange}
                    onChange={(event) => onChange(member.id, { role: event.target.value })}
                  >
                    <option>Analyst</option>
                    <option>SQA Engineer</option>
                    <option>Manager</option>
                  </select>
                )}
              </td>
              <td className="px-4 py-3"><Badge value={member.status} /></td>
              <td className="px-4 py-3 tabular-nums text-ink">{member.workload}</td>
              <td className="px-4 py-3 text-right">
                <div className="inline-flex flex-wrap items-center justify-end gap-2">
                  {onProjectAccess && ['Analyst', 'SQA Engineer'].includes(member.role) && (
                    <button
                      type="button"
                      className="rounded-md border border-line bg-surface px-2.5 py-1 text-[11px] font-medium text-ink hover:border-accent/40"
                      disabled={busy}
                      onClick={() => onProjectAccess(member.id, !member.project_access)}
                    >
                      {member.project_access ? 'Revoke project access' : 'Grant project access'}
                    </button>
                  )}
                  {member.role === 'admin' ? (
                    <span className="text-[11px] text-muted">Organization administrator</span>
                  ) : onChange ? (
                    <button
                      type="button"
                      className="rounded-md border border-line bg-surface-alt px-2.5 py-1 text-[11px] font-medium text-ink hover:border-danger/40"
                      disabled={busy}
                      onClick={() => onChange(member.id, { is_active: member.status !== 'Active' })}
                    >
                      {member.status === 'Active' ? 'Disable account' : 'Enable account'}
                    </button>
                  ) : (
                    <a className="font-medium text-accent hover:underline" href="#admin/team">Manage</a>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Workload({ members, onSelect }) {
  return (
    <Panel title="Reviewer Workload" subtitle="Open assignments and completed reviews · no performance ranking">
      {!members.length ? (
        <Empty>No SQA Engineers have joined yet.</Empty>
      ) : (
        <div className="table-wrapper" tabIndex={0} role="region" aria-label="Reviewer workload">
          <table className="min-w-[540px] text-left text-xs">
            <caption className="visually-hidden">SQA Engineer workload</caption>
            <thead>
              <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wider text-muted">
                <th scope="col" className="px-4 py-3">SQA Engineer</th>
                <th scope="col" className="px-4 py-3">Assigned</th>
                <th scope="col" className="px-4 py-3">Pending</th>
                <th scope="col" className="px-4 py-3">Completed</th>
                <th scope="col" className="px-4 py-3">High-risk open</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {members.map((member) => (
                <tr key={member.id} className="hover:bg-surface-alt/50">
                  <td className="px-4 py-3">
                    <button type="button" className="font-semibold text-accent hover:underline" onClick={() => onSelect(member.id)}>
                      {member.name}
                    </button>
                    {member.status === 'Disabled' && <span className="ml-2 text-[11px] text-danger">Disabled</span>}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{member.assigned}</td>
                  <td className="px-4 py-3 tabular-nums">{member.pending}</td>
                  <td className="px-4 py-3 tabular-nums">{member.completed}</td>
                  <td className="px-4 py-3 tabular-nums">{member.high_risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
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
    event.preventDefault();
    setError('');
    if (password && newPassword !== confirm) {
      setError('Passwords must match.');
      return;
    }
    setBusy(true);
    try {
      const result = await api(password ? '/api/auth/change-password' : '/api/admin/settings', {
        method: password ? 'POST' : 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(password ? { current_password: currentPassword, new_password: newPassword } : { name, overdue_days: Number(days) }),
      });
      if (password) onSignedOut(result.message);
      else onSaved(result.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {user.role === 'admin' && tab !== 'password' && <div className="lg:col-span-2"><ProjectContext editable /></div>}
      {error && <p className="lg:col-span-2 rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}

      <Panel title="My Profile" subtitle="Your organization administrator account">
        <div className="flex items-center gap-4">
          <span className="inline-flex size-12 items-center justify-center rounded-full bg-accent-tint text-sm font-bold text-accent">
            {user.name.slice(0, 2).toUpperCase()}
          </span>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-ink">{user.name}</h3>
            <p className="text-xs text-muted">{user.email}</p>
            <Badge value={user.role === 'admin' ? 'SQA Admin' : user.role} />
          </div>
        </div>
      </Panel>

      {tab !== 'password' && (
        <Panel title="Organization Settings" subtitle="Used in this workspace and its review attention queue">
          <form className="space-y-3" onSubmit={(event) => save(event)}>
            <label className="block space-y-1 text-xs font-medium text-muted">
              <span>Organization / company name</span>
              <input className={inputClass} required minLength={2} maxLength={100} value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="block space-y-1 text-xs font-medium text-muted">
              <span>Flag pending reviews after (days)</span>
              <input className={inputClass} type="number" required min={1} max={90} value={days} onChange={(event) => setDays(event.target.value)} />
            </label>
            <button type="submit" className={buttonPrimaryClass} disabled={busy}>Save settings</button>
          </form>
        </Panel>
      )}

      {tab !== 'profile' && (
        <Panel title="Change Password" subtitle="Changing your password signs out all existing sessions">
          <form className="space-y-3" onSubmit={(event) => save(event, true)}>
            <label className="block space-y-1 text-xs font-medium text-muted">
              <span>Current password</span>
              <input className={inputClass} type="password" autoComplete="current-password" required maxLength={128} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
            </label>
            <label className="block space-y-1 text-xs font-medium text-muted">
              <span>New password</span>
              <input className={inputClass} type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </label>
            <label className="block space-y-1 text-xs font-medium text-muted">
              <span>Confirm new password</span>
              <input className={inputClass} type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
            </label>
            <button type="submit" className={buttonPrimaryClass} disabled={busy}>Update password</button>
          </form>
        </Panel>
      )}
    </div>
  );
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
  const [search, setSearch] = useState('');

  useEffect(() => {
    const update = () => {
      setRoute(readRoute());
      setMenu(false);
      setNotifications(false);
      setNotice('');
    };
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
    setLoading(true);
    setError('');
    const options = { signal: controller.signal };
    Promise.all([
      api(`/api/admin/dashboard?${query}`, options),
      showList ? api(`/api/admin/requirements?${query}`, options) : Promise.resolve(null),
    ])
      .then(([dashboard, rows]) => {
        if (!controller.signal.aborted) {
          setData(dashboard);
          setListing(rows);
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query, showList, revision]);

  function navigate(section, changes = {}, retain = true) {
    const next = new URLSearchParams(retain ? query : '');
    next.delete('page');
    Object.entries(changes).forEach(([key, value]) => {
      if (value === '' || value === null) next.delete(key);
      else next.set(key, String(value));
    });
    window.location.hash = `admin${section === 'dashboard' ? '' : `/${section}`}${next.size ? `?${next}` : ''}`;
  }

  function saved(message) {
    setNotice(message);
    setRevision((value) => value + 1);
  }

  async function changeMember(id, change) {
    setBusy(true);
    setError('');
    try {
      const result = await api(`/api/admin/users/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(change),
      });
      saved(result.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const reviewers = data?.team.filter((member) => member.role === 'SQA Engineer') || [];
  const title =
    route.section === 'dashboard'
      ? user.role === 'admin'
        ? 'Admin Quality Dashboard'
        : 'Manager Dashboard'
      : route.section === 'detail'
        ? `Requirement REQ-${route.id}`
        : NAV.find(([key]) => key === route.section)?.[1] || 'Dashboard';

  useEffect(() => {
    document.title = `ReqQuality AI | ${title}`;
  }, [title]);

  const filterVisible = ['dashboard', 'requirements', 'reviews', 'traceability', 'projects'].includes(route.section);
  const link = (label, section, changes) => (
    <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline" onClick={() => navigate(section, changes)}>
      {label} <Icon name="arrow" size={14} />
    </button>
  );
  const invite = () => navigate('invitations', { invite: 1 }, false);
  const trace = data?.traceability;

  const navGroups = [
    {
      title: 'Workspace',
      items: ['dashboard', 'projects', 'requirements', 'reviews', 'traceability', 'reports'].map((key) => ({
        key,
        label: NAV.find(([k]) => k === key)[1],
        href: `#admin${key === 'dashboard' ? '' : `/${key}`}`,
        Icon: ADMIN_NAV_ICONS[key],
        active: route.section === key || (route.section === 'detail' && key === 'requirements'),
        badge: key === 'reviews' ? data?.summary.pending_reviews || 0 : 0,
      })),
    },
    {
      title: 'Admin',
      items: ['team', 'invitations', 'permissions', 'activity', 'settings'].map((key) => ({
        key,
        label: NAV.find(([k]) => k === key)[1],
        href: `#admin/${key}`,
        Icon: ADMIN_NAV_ICONS[key],
        active: route.section === key,
      })),
    },
  ];

  const searchSlot = (
    <form
      className="hidden md:flex items-center gap-2 rounded-lg border border-line bg-surface-alt/60 px-2.5 py-1.5 w-52 lg:w-64"
      onSubmit={(event) => {
        event.preventDefault();
        navigate('requirements', { q: search }, false);
      }}
    >
      <Search className="size-3.5 text-muted shrink-0" aria-hidden="true" />
      <input
        className="w-full bg-transparent text-xs text-ink placeholder:text-muted focus:outline-none border-0"
        aria-label="Search requirements"
        placeholder="Search requirements…"
        maxLength={200}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
    </form>
  );

  const actionsSlot = (
    <div className="relative flex items-center gap-1.5">
      <button
        type="button"
        className="relative inline-flex size-8 items-center justify-center rounded-lg border border-line bg-surface text-muted hover:text-ink"
        aria-label="Review notifications"
        aria-expanded={notifications}
        onClick={() => {
          setNotifications((v) => !v);
          setMenu(false);
        }}
      >
        <Bell className="size-4" aria-hidden="true" />
        {data?.attention_total > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-warning" />}
      </button>

      <button
        type="button"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-surface-alt"
        onClick={() => {
          setMenu((v) => !v);
          setNotifications(false);
        }}
        aria-expanded={menu}
        aria-label="Open profile menu"
      >
        <Shield className="size-3.5 text-accent" aria-hidden="true" />
        <span className="hidden sm:inline max-w-[110px] truncate">{user.name}</span>
        <ChevronDown className="size-3.5 text-muted" aria-hidden="true" />
      </button>

      {notifications && (
        <div className="absolute right-0 top-11 z-40 w-64 rounded-xl border border-line bg-surface p-4 shadow-lg text-xs space-y-2">
          <strong className="block text-ink">Review attention</strong>
          <p className="text-muted">
            {data?.summary.pending_reviews || 0} pending reviews · {data?.summary.overdue || 0} overdue
          </p>
          {link('Open attention queue', 'requirements', { quality: 'attention' })}
        </div>
      )}

      {menu && (
        <div className="absolute right-0 top-11 z-40 w-52 rounded-xl border border-line bg-surface p-1.5 shadow-lg text-xs grid gap-0.5">
          <a className="rounded-lg px-3 py-2 text-ink hover:bg-surface-alt no-underline" href="#admin/settings?tab=profile">My Profile</a>
          <a className="rounded-lg px-3 py-2 text-ink hover:bg-surface-alt no-underline" href="#admin/settings">Organization Settings</a>
          <a className="rounded-lg px-3 py-2 text-ink hover:bg-surface-alt no-underline" href="#admin/settings?tab=password">Change Password</a>
          <button type="button" className="rounded-lg px-3 py-2 text-left font-medium text-danger hover:bg-danger-tint" onClick={onLogout}>
            Logout
          </button>
        </div>
      )}
    </div>
  );

  const riskChartData = data
    ? [
        ...(data.risk_distribution || []).map((item) => ({ name: item.label, count: item.count })),
        { name: 'Unscored', count: data.unscored || 0 },
      ]
    : [];

  return (
    <WorkspaceShell
      user={user}
      page={route.section}
      breadcrumb={title}
      navGroups={navGroups}
      searchSlot={searchSlot}
      actionsSlot={actionsSlot}
      onLogout={onLogout}
    >
      <div className="space-y-6">
        {(error || logoutError) && (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-danger/35 bg-danger-tint px-4 py-3 text-xs text-danger" role="alert">
            <span>{error || logoutError}</span>
            <button type="button" className={buttonSecondaryClass} onClick={() => setRevision((value) => value + 1)}>Retry</button>
          </div>
        )}
        {notice && (
          <p className="rounded-xl border border-success/30 bg-success-tint px-4 py-2.5 text-xs font-medium text-success" role="status">
            {notice}
          </p>
        )}

        {filterVisible && (
          <Filters
            values={filters}
            reviewers={reviewers}
            onChange={(key, value) => navigate(route.section, { [key]: value })}
            onReset={() => navigate(route.section, {}, false)}
          />
        )}

        {filterVisible && (filters.get('q') || filters.get('quality')) && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {filters.get('q') && <span className="rounded-md border border-line bg-surface px-2.5 py-1 text-ink">Search: {filters.get('q')}</span>}
            {filters.get('quality') && (
              <span className="rounded-md border border-line bg-surface px-2.5 py-1 text-ink">
                Quality: {QUALITY.find(([key]) => key === filters.get('quality'))?.[1] || filters.get('quality').replaceAll('_', ' ')}
              </span>
            )}
            <button type="button" className={buttonSecondaryClass} onClick={() => navigate(route.section, { q: '', quality: '' })}>Clear</button>
          </div>
        )}

        {loading && <LoadingSkeleton label="Loading quality workspace" />}
        {!loading && !data && <Empty>Dashboard data is unavailable. Use Retry to reconnect.</Empty>}

        {data && !error && (
          <>
            {filterVisible && <p className="text-xs text-muted">{data.scope_note}</p>}

            {route.section === 'dashboard' && (
              <>
                <PageHeader
                  eyebrow="Organization Overview"
                  title="Quality at a glance"
                  description="Keep reviews moving and focus your team where quality needs attention."
                  actions={
                    <>
                      <button type="button" className={buttonSecondaryClass} onClick={() => setRevision((value) => value + 1)}>
                        <RefreshCw className="size-3.5" aria-hidden="true" />
                        Refresh
                      </button>
                      <button type="button" className={buttonPrimaryClass} onClick={invite}>
                        <Plus className="size-3.5" aria-hidden="true" />
                        Invite User
                      </button>
                    </>
                  }
                />
                <QualityMetrics data={data.integrated} />
                <DashboardCharts
                  riskData={riskChartData}
                  executionCounts={data.integrated?.latest_execution_counts}
                  bugSeverityCounts={data.integrated?.open_bugs_by_severity}
                />
                <section className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-xs shadow-xs" aria-label="Quick actions">
                  <strong className="mr-1 text-ink">Quick actions:</strong>
                  <button type="button" className={buttonSecondaryClass} onClick={invite}>Invite Team Member</button>
                  <button type="button" className={buttonSecondaryClass} onClick={() => navigate('reviews', { review: 'pending-reviews' })}>View Pending Reviews</button>
                  <button type="button" className={buttonSecondaryClass} onClick={() => navigate('requirements', { risk: 'high-critical' })}>View High-Risk</button>
                  <a className={`${buttonSecondaryClass} no-underline`} href="#admin/team">Manage Team</a>
                  <a className={`${buttonSecondaryClass} no-underline`} href="#admin/reports">Open Reports</a>
                </section>
                <Workload members={data.reviewer_workload} onSelect={(id) => navigate('requirements', { reviewer: id })} />
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Panel
                    title="Team Overview"
                    subtitle="People and current review capacity"
                    action={<a className="text-xs font-semibold text-accent hover:underline" href="#admin/team">Manage Team →</a>}
                  >
                    <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4 text-xs">
                      {[
                        ['Members', data.team_summary.total],
                        ['Analysts', data.team_summary.analysts],
                        ['SQA Engineers', data.team_summary.engineers],
                        ['Active', data.team_summary.active],
                      ].map(([label, val]) => (
                        <div key={label} className="rounded-lg border border-line bg-surface-alt/60 p-2.5">
                          <strong className="block text-base font-semibold text-ink tabular-nums">{val}</strong>
                          <span className="text-[11px] text-muted">{label}</span>
                        </div>
                      ))}
                    </div>
                    <ul className="divide-y divide-line">
                      {data.team.slice(0, 5).map((member) => (
                        <li key={member.id} className="flex items-center justify-between gap-3 py-2.5 text-xs">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-accent-tint text-[11px] font-semibold text-accent">
                              {member.name.slice(0, 2).toUpperCase()}
                            </span>
                            <div className="min-w-0">
                              <strong className="block truncate text-ink">{member.name}</strong>
                              <small className="block truncate text-[11px] text-muted">{member.email}</small>
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            <span className="block font-medium text-ink">{member.role === 'admin' ? 'SQA Admin' : member.role}</span>
                            <small className="text-[11px] text-muted">{member.status} · {member.workload} open</small>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-3 text-[11px]">
                      {Object.entries(data.invitations).map(([status, count]) => (
                        <a href="#admin/invitations" key={status} className="rounded-md border border-line bg-surface-alt px-2.5 py-1 text-ink no-underline hover:border-accent/40">
                          <strong>{count}</strong> {status}
                        </a>
                      ))}
                    </div>
                  </Panel>

                  <Panel
                    title="Recent Activity"
                    subtitle="Recorded team actions"
                    action={<a className="text-xs font-semibold text-accent hover:underline" href="#admin/activity">View All →</a>}
                  >
                    <ActivityList items={data.activity.slice(0, 6)} />
                  </Panel>
                </div>
              </>
            )}

            {showList && (
              <Panel title={route.section === 'reviews' ? 'SQA Review Queue' : 'Requirements'} subtitle={`${listing?.total || 0} matching requirements`}>
                <RequirementTable rows={listing?.requirements || []} pending={route.section === 'reviews'} onAssign={setAssignment} />
                <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3 text-xs">
                  <button type="button" className={buttonSecondaryClass} disabled={!listing || listing.page <= 1} onClick={() => navigate(route.section, { page: listing.page - 1 })}>Previous</button>
                  <span className="text-muted tabular-nums">
                    Page {listing?.page || 1} of {Math.max(1, Math.ceil((listing?.total || 0) / (listing?.page_size || 20)))}
                  </span>
                  <button type="button" className={buttonSecondaryClass} disabled={!listing || listing.page * listing.page_size >= listing.total} onClick={() => navigate(route.section, { page: listing.page + 1 })}>Next</button>
                </div>
              </Panel>
            )}

            {route.section === 'detail' && (
              <>
                <p className="text-xs text-muted">SQA Admin inspects and assigns reviews. Authorized reviewers record review decisions.</p>
                <RequirementDetails
                  requirementId={route.id}
                  user={user}
                  csrfToken={csrfToken}
                  managerView
                  revision={revision}
                  onAssign={setAssignment}
                  openReview={params.get('review') === '1'}
                />
              </>
            )}

            {route.section === 'team' && (
              <div className="space-y-6">
                <PageHeader
                  eyebrow="Team Management"
                  title="Your quality team"
                  description="Manage access and supported roles. Disabled or reassigned users lose their existing sessions."
                  actions={
                    <button type="button" className={buttonPrimaryClass} onClick={invite}>
                      <Plus className="size-3.5" aria-hidden="true" />
                      Invite Team Member
                    </button>
                  }
                />
                <Panel title="Registered members" subtitle={`${data.team_summary.active} active of ${data.team_summary.total} members`}>
                  <TeamTable
                    members={data.team}
                    onChange={changeMember}
                    onProjectAccess={
                      user.role === 'admin'
                        ? async (id, enabled) => {
                            setBusy(true);
                            setError('');
                            try {
                              await api(`/api/admin/users/${id}/project-access`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ enabled }),
                              });
                              saved('Project access updated.');
                            } catch (e) {
                              setError(e.message);
                            } finally {
                              setBusy(false);
                            }
                          }
                        : null
                    }
                    busy={busy}
                  />
                </Panel>
                <Panel title="Invited members" subtitle="Valid pending invitations">
                  {!data.invited_members.length ? (
                    <Empty>No pending invitations.</Empty>
                  ) : (
                    <ul className="divide-y divide-line">
                      {data.invited_members.map((member) => (
                        <li key={member.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-xs">
                          <div>
                            <strong className="text-ink">{member.name}</strong>
                            <small className="block text-muted">{member.email}</small>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge value={member.role} />
                            <Badge value="Invited" />
                            <a className="font-medium text-accent hover:underline" href="#admin/invitations">Manage invitation</a>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Panel>
                <Workload members={data.reviewer_workload} onSelect={(id) => navigate('requirements', { reviewer: id }, false)} />
              </div>
            )}

            {route.section === 'invitations' && (
              <Admin csrfToken={csrfToken} initialInvite={params.get('invite') === '1'} onChanged={() => setRevision((value) => value + 1)} />
            )}

            {route.section === 'traceability' && (
              <Panel
                title="Traceability Overview"
                subtitle="Current requirements with every criterion explicitly linked to a current case. Recorded links do not prove complete coverage."
              >
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {[
                    ['With acceptance criteria', trace.with_criteria, 'has_criteria'],
                    ['With test scenarios', trace.with_tests, 'has_tests'],
                    ['Reviewed by SQA', trace.reviewed, 'reviewed'],
                    ['All criteria explicitly linked', trace.fully_traceable, 'traceable'],
                    ['Missing traceability links', trace.missing_links, 'traceability_gaps'],
                  ].map(([label, count, quality]) => (
                    <button
                      type="button"
                      key={label}
                      className="rounded-xl border border-line bg-surface-alt/50 p-3.5 text-left hover:border-accent/50"
                      onClick={() => navigate('requirements', { quality })}
                    >
                      <strong className="block text-2xl font-bold text-ink tabular-nums">{count}</strong>
                      <span className="mt-1 block text-xs text-muted">{label}</span>
                    </button>
                  ))}
                </div>
                <div className="mt-5 space-y-2">
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-alt">
                    <div className="h-full rounded-full bg-accent-strong" style={{ width: `${trace.coverage}%` }} />
                  </div>
                  <p className="text-xs text-muted">
                    {trace.coverage}% have all criteria explicitly linked. Review and execution success are separate; links do not prove complete coverage.
                  </p>
                  <button type="button" className={buttonPrimaryClass} onClick={() => navigate('requirements', { quality: 'traceability_gaps' })}>
                    Inspect missing links
                  </button>
                </div>
              </Panel>
            )}

            {route.section === 'projects' && (
              <Panel title="Project Overview" subtitle="This installation currently stores one shared project">
                <div className="flex flex-col gap-4 rounded-xl border border-line bg-surface-alt/40 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex size-10 items-center justify-center rounded-xl bg-accent-tint text-accent">
                      <Icon name="projects" size={20} />
                    </span>
                    <div>
                      <h3 className="text-base font-semibold text-ink">ReqQuality AI</h3>
                      <p className="text-xs text-muted">{data.summary.total} requirements · {data.summary.analyzed} analyzed</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-xs">
                    <span><strong className="text-ink tabular-nums">{data.summary.pending_reviews}</strong> <span className="text-muted">Pending</span></span>
                    <span><strong className="text-ink tabular-nums">{data.summary.approved}</strong> <span className="text-muted">Approved</span></span>
                    <span><strong className="text-danger tabular-nums">{data.summary.high_risk}</strong> <span className="text-muted">High risk</span></span>
                    <button type="button" className={buttonPrimaryClass} onClick={() => navigate('requirements', { project: 'current' })}>Open project</button>
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-alt">
                    <div className="h-full rounded-full bg-success" style={{ width: `${data.summary.total ? (data.summary.approved * 100) / data.summary.total : 0}%` }} />
                  </div>
                  <p className="text-xs text-muted">
                    Review progress: {data.summary.total ? Math.round((data.summary.approved * 100) / data.summary.total) : 0}% approved. This workspace contains one shared project.
                  </p>
                </div>
              </Panel>
            )}

            {route.section === 'reports' && (
              <Panel title="Quality Reports" subtitle="Exports include all requirements in the current shared project">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <article className="rounded-xl border border-line bg-surface-alt/40 p-5 space-y-3">
                    <Icon name="reports" size={24} className="text-accent" />
                    <h3 className="text-sm font-semibold text-ink">Project quality report</h3>
                    <p className="text-xs text-muted">Review progress, risk, scenarios, and requirement traceability.</p>
                    <PdfExportButton url="/api/reports/project.pdf" filename="project-quality-report.pdf">Download PDF</PdfExportButton>
                  </article>
                  <article className="rounded-xl border border-line bg-surface-alt/40 p-5 space-y-3">
                    <Icon name="requirements" size={24} className="text-success" />
                    <h3 className="text-sm font-semibold text-ink">Requirements register</h3>
                    <p className="text-xs text-muted">Export the existing requirement fields for further analysis.</p>
                    <PdfExportButton url="/api/exports/requirements.csv" filename="requirements.csv" format="CSV">Download CSV</PdfExportButton>
                  </article>
                </div>
              </Panel>
            )}

            {route.section === 'activity' && (
              <Panel title="Activity Logs" subtitle="Latest 50 recorded events">
                <ActivityList items={data.activity} />
              </Panel>
            )}

            {route.section === 'permissions' && <RolePermissions csrfToken={csrfToken} />}

            {route.section === 'settings' && (
              <Settings
                key={params.get('tab') || 'organization'}
                organization={data.organization}
                user={user}
                csrfToken={csrfToken}
                onSaved={saved}
                onSignedOut={onSignedOut}
                tab={params.get('tab')}
              />
            )}
          </>
        )}
      </div>
      {assignment && <AssignmentDialog row={assignment} reviewers={reviewers} csrfToken={csrfToken} onClose={() => setAssignment(null)} onSaved={saved} />}
    </WorkspaceShell>
  );
}
