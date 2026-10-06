import React, { useEffect, useState } from 'react';

export default function Admin({ csrfToken, initialInvite = false, onChanged }) {
  const [invitations, setInvitations] = useState([]);
  const [showForm, setShowForm] = useState(initialInvite);
  const [form, setForm] = useState({ name: '', email: '', role: 'SQA Engineer' });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  async function load() {
    try {
      const response = await fetch('/api/admin/invitations', { credentials: 'include' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load invitations.');
      setInvitations(data.invitations);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => { if (initialInvite) setShowForm(true); }, [initialInvite]);
  async function act(path, body) {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await fetch(path, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, body: JSON.stringify(body || {}) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to complete this action.');
      setNotice(data.message); setShowForm(false); setSelected(null);
    } catch (err) { setError(err.message); }
    finally { await load(); setBusy(false); onChanged?.(); }
  }
  function submitInvitation(event) {
    event.preventDefault();
    const name = form.name.trim();
    const email = form.email.trim().toLowerCase();
    if (name.length < 2 || name.length > 80 || /[\u0000-\u001f]/.test(name)) {
      setError('Name must be between 2 and 80 characters.'); return;
    }
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Enter a valid email address.'); return;
    }
    if (!['Manager', 'SQA Engineer', 'Analyst'].includes(form.role)) {
      setError('Choose Manager, SQA Engineer or Analyst.'); return;
    }
    act('/api/admin/invitations', { name, email, role: form.role });
  }
  const date = (value) => value ? new Date(value).toLocaleString() : '—';
  return <section className="card invitation-panel">
    <p className="eyebrow">ADMIN PANEL</p><h1>Invitations / User Management</h1>
    <p>Invite Managers, Analysts and SQA Engineers. Links expire after 24 hours.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="success" role="status">{notice}</p>}
    <button className="requirement-save-button" disabled={busy} onClick={() => setShowForm(!showForm)}>{showForm ? 'Cancel' : 'Invite User'}</button>
    {showForm && <form className="auth-form invitation-form" onSubmit={submitInvitation}>
      <div className="requirement-field"><label htmlFor="invite-name">Full Name</label><input id="invite-name" autoComplete="name" required minLength={2} maxLength={80} disabled={busy} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="requirement-field"><label htmlFor="invite-email">Email Address</label><input id="invite-email" type="email" autoComplete="email" required maxLength={254} disabled={busy} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
      <div className="requirement-field"><label htmlFor="invite-role">Role</label><select id="invite-role" disabled={busy} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option>SQA Engineer</option><option>Manager</option><option>Analyst</option></select></div>
      <button className="requirement-save-button" disabled={busy}>{busy ? 'Sending...' : 'Generate Invitation'}</button>
    </form>}
    {loading ? <p role="status">Loading invitations...</p> : <div className="invitation-table-wrap"><table className="invitation-table"><caption>Existing invitations</caption><thead><tr>{['Name', 'Email', 'Role', 'Status', 'Created', 'Expires', 'Accepted', 'Email delivery', 'Actions'].map((heading) => <th key={heading} scope="col">{heading}</th>)}</tr></thead><tbody>
      {invitations.map((row) => <tr key={row.id}><td>{row.name}</td><td>{row.email}</td><td>{row.role}</td><td>{row.status}</td><td>{date(row.created_at)}</td><td>{date(row.expires_at)}</td><td>{date(row.accepted_at)}</td><td>{row.delivery_status}</td><td className="invitation-actions">
        <button disabled={busy} onClick={() => setSelected(row)}>View</button>
        {['pending', 'expired'].includes(row.status) && <button disabled={busy} onClick={() => act(`/api/admin/invitations/${row.id}/resend`)}>Resend / regenerate</button>}
        {row.status === 'pending' && <button disabled={busy} onClick={() => act(`/api/admin/invitations/${row.id}/revoke`)}>Revoke</button>}
      </td></tr>)}
      {!invitations.length && <tr><td colSpan={9}>No invitations yet.</td></tr>}
    </tbody></table></div>}
    {selected && <section className="invitation-details" aria-label="Invitation details"><h2>{selected.name}</h2><p>{selected.email} · {selected.role} · {selected.status}</p><p>Failed attempts: {selected.failed_attempts}</p><p>Temporary lock: {date(selected.temporarily_locked_until)}</p><p>Last failed attempt: {date(selected.last_failed_attempt_at)}</p><p>Created: {date(selected.created_at)}</p><p>Expires: {date(selected.expires_at)}</p><p>Accepted: {date(selected.accepted_at)}</p><button onClick={() => setSelected(null)}>Close details</button></section>}
  </section>;
}
