import { apiFetch as fetch } from '../api.js';
import React, { useEffect, useState } from 'react';
import { Mail, Plus, X } from 'lucide-react';
import { StatusBadge, buttonPrimaryClass, buttonSecondaryClass, inputClass } from '../components/ui';

export default function Admin({ csrfToken, initialInvite = false, onChanged }) {
  const [invitations, setInvitations] = useState([]);
  const [showForm, setShowForm] = useState(initialInvite);
  const [form, setForm] = useState({ name: '', email: '', role: 'SQA Engineer' });
  const [touched, setTouched] = useState({ name: false, email: false });
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => { if (initialInvite) setShowForm(true); }, [initialInvite]);

  async function act(path, body) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const response = await fetch(path, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(body || {}),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to complete this action.');
      setNotice(data.message);
      setShowForm(false);
      setSelected(null);
    } catch (err) {
      setError(err.message);
    } finally {
      await load();
      setBusy(false);
      onChanged?.();
    }
  }

  function submitInvitation(event) {
    event.preventDefault();
    setTouched({ name: true, email: true });
    const name = form.name.trim();
    const email = form.email.trim().toLowerCase();
    if (name.length < 2 || name.length > 80 || /[\u0000-\u001f]/.test(name)) {
      setError('Name must be between 2 and 80 characters.');
      return;
    }
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Enter a valid email address.');
      return;
    }
    if (!['Manager', 'SQA Engineer', 'Analyst'].includes(form.role)) {
      setError('Choose Manager, SQA Engineer or Analyst.');
      return;
    }
    act('/api/admin/invitations', { name, email, role: form.role });
  }

  const nameInvalid = touched.name && (form.name.trim().length < 2 || form.name.trim().length > 80);
  const emailInvalid = touched.email && (!form.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()));
  const date = (value) => (value ? new Date(value).toLocaleString() : '—');

  return (
    <section className="card invitation-panel rounded-xl border border-line bg-surface p-5 shadow-xs space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="eyebrow text-[11px] font-semibold uppercase tracking-wider text-accent">Admin Panel</p>
          <h1 className="text-lg font-bold text-ink">Invitations &amp; User Onboarding</h1>
          <p className="text-xs text-muted">Invite Managers, Analysts, and SQA Engineers. Links expire after 24 hours.</p>
        </div>
        <button type="button" className={showForm ? buttonSecondaryClass : buttonPrimaryClass} disabled={busy} onClick={() => setShowForm(!showForm)}>
          {showForm ? <X className="size-3.5" aria-hidden="true" /> : <Plus className="size-3.5" aria-hidden="true" />}
          {showForm ? 'Cancel' : 'Invite User'}
        </button>
      </div>

      {error && <p className="error rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
      {notice && <p className="success rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">{notice}</p>}

      {showForm && (
        <form className="auth-form invitation-form grid grid-cols-1 gap-4 rounded-xl border border-line bg-surface-alt/50 p-4 md:grid-cols-3" onSubmit={submitInvitation}>
          <div className="requirement-field space-y-1">
            <label htmlFor="invite-name" className="block text-xs font-semibold text-ink">Full Name</label>
            <span id="invite-name-hint" className="block text-[11px] text-muted">2 to 80 characters</span>
            <input
              id="invite-name"
              className={inputClass}
              autoComplete="name"
              required
              minLength={2}
              maxLength={80}
              aria-invalid={nameInvalid ? 'true' : 'false'}
              aria-describedby={nameInvalid ? 'invite-name-hint invite-name-error' : 'invite-name-hint'}
              disabled={busy}
              value={form.name}
              onBlur={() => setTouched((prev) => ({ ...prev, name: true }))}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            {nameInvalid && <p id="invite-name-error" className="text-xs text-danger">Name must be between 2 and 80 characters.</p>}
          </div>

          <div className="requirement-field space-y-1">
            <label htmlFor="invite-email" className="block text-xs font-semibold text-ink">Email Address</label>
            <span id="invite-email-hint" className="block text-[11px] text-muted">Format: member@company.com</span>
            <input
              id="invite-email"
              className={inputClass}
              type="email"
              autoComplete="email"
              required
              maxLength={254}
              aria-invalid={emailInvalid ? 'true' : 'false'}
              aria-describedby={emailInvalid ? 'invite-email-hint invite-email-error' : 'invite-email-hint'}
              disabled={busy}
              value={form.email}
              onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            {emailInvalid && <p id="invite-email-error" className="text-xs text-danger">Enter a valid email address.</p>}
          </div>

          <div className="requirement-field space-y-1">
            <label htmlFor="invite-role" className="block text-xs font-semibold text-ink">Role</label>
            <span className="block text-[11px] text-muted">Assigned automatically upon acceptance</span>
            <select
              id="invite-role"
              className={inputClass}
              disabled={busy}
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option>SQA Engineer</option>
              <option>Manager</option>
              <option>Analyst</option>
            </select>
          </div>

          <div className="md:col-span-3 flex justify-end">
            <button type="submit" className={buttonPrimaryClass} disabled={busy}>
              <Mail className="size-3.5" aria-hidden="true" />
              {busy ? 'Sending...' : 'Generate Invitation'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-xs text-muted" role="status">Loading invitations…</p>
      ) : (
        <div className="table-wrapper" tabIndex={0} role="region" aria-label="Existing invitations">
          <table className="invitation-table min-w-[820px] text-left text-xs">
            <caption className="visually-hidden">Existing invitations</caption>
            <thead>
              <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wider text-muted">
                {['Name', 'Email', 'Role', 'Status', 'Created', 'Expires', 'Accepted', 'Email delivery', 'Actions'].map((heading) => (
                  <th key={heading} scope="col" className="px-3 py-2.5">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {invitations.map((row) => (
                <tr key={row.id} className="hover:bg-surface-alt/50">
                  <td className="px-3 py-2.5 font-semibold text-ink">{row.name}</td>
                  <td className="px-3 py-2.5 text-muted">{row.email}</td>
                  <td className="px-3 py-2.5"><StatusBadge value={row.role} /></td>
                  <td className="px-3 py-2.5"><StatusBadge value={row.status} /></td>
                  <td className="px-3 py-2.5 text-muted whitespace-nowrap">{date(row.created_at)}</td>
                  <td className="px-3 py-2.5 text-muted whitespace-nowrap">{date(row.expires_at)}</td>
                  <td className="px-3 py-2.5 text-muted whitespace-nowrap">{date(row.accepted_at)}</td>
                  <td className="px-3 py-2.5 text-muted">{row.delivery_status}</td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <button type="button" className="rounded-md border border-line bg-surface px-2 py-1 text-[11px] font-medium text-ink hover:border-accent/40" disabled={busy} onClick={() => setSelected(row)}>
                        View
                      </button>
                      {['pending', 'expired'].includes(row.status) && (
                        <button type="button" className="rounded-md border border-line bg-surface-alt px-2 py-1 text-[11px] font-medium text-accent hover:border-accent/40" disabled={busy} onClick={() => act(`/api/admin/invitations/${row.id}/resend`)}>
                          Resend
                        </button>
                      )}
                      {row.status === 'pending' && (
                        <button type="button" className="rounded-md border border-danger/30 bg-danger-tint px-2 py-1 text-[11px] font-medium text-danger" disabled={busy} onClick={() => act(`/api/admin/invitations/${row.id}/revoke`)}>
                          Revoke
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {!invitations.length && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-xs text-muted">No invitations yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <section className="invitation-details rounded-xl border border-line bg-surface-alt/50 p-4 text-xs space-y-2" aria-label="Invitation details">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-ink">{selected.name}</h2>
            <button type="button" className={buttonSecondaryClass} onClick={() => setSelected(null)}>Close details</button>
          </div>
          <p className="text-muted">{selected.email} · {selected.role} · <StatusBadge value={selected.status} /></p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 text-muted">
            <p>Failed attempts: <strong className="text-ink">{selected.failed_attempts}</strong></p>
            <p>Temporary lock: <strong className="text-ink">{date(selected.temporarily_locked_until)}</strong></p>
            <p>Last failed attempt: <strong className="text-ink">{date(selected.last_failed_attempt_at)}</strong></p>
            <p>Created: <strong className="text-ink">{date(selected.created_at)}</strong></p>
            <p>Expires: <strong className="text-ink">{date(selected.expires_at)}</strong></p>
            <p>Accepted: <strong className="text-ink">{date(selected.accepted_at)}</strong></p>
          </div>
        </section>
      )}
    </section>
  );
}
