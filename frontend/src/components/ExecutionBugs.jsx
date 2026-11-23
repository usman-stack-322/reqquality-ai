import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api.js';
import { StatusBadge, buttonPrimaryClass, buttonSecondaryClass, inputClass } from './ui';

const fields = ['title', 'preconditions', 'steps_to_reproduce', 'expected_result', 'actual_result', 'severity', 'priority', 'environment', 'build', 'evidence_reference'];
const editable = (bug) => Object.fromEntries(fields.map((key) => [key, bug[key]]));
const lines = (value) => value.split('\n').map((v) => v.trim()).filter(Boolean);

function showSource(event, id) {
  const element = document.getElementById(id);
  if (!element) return;
  event.preventDefault();
  if (element.tagName === 'DETAILS') element.open = true;
  element.scrollIntoView({ block: 'center' });
}

function BugForm({ initial, busy, save, label }) {
  const [value, setValue] = useState(editable(initial));
  const [preconditions, setPreconditions] = useState(initial.preconditions.join('\n'));
  const [steps, setSteps] = useState(initial.steps_to_reproduce.join('\n'));
  const set = (key, v) => setValue((old) => ({ ...old, [key]: v }));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save({ ...value, preconditions: lines(preconditions), steps_to_reproduce: lines(steps) });
      }}
      className="rounded-xl border border-line bg-surface-alt/40 p-4"
    >
      <fieldset disabled={busy} className="space-y-3">
        <legend className="text-xs font-semibold uppercase tracking-wider text-accent">{label}</legend>
        <p className="text-xs text-muted">Review and edit the supplied execution details before saving. Severity and priority are separate decisions.</p>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Bug title</span>
          <input className={inputClass} required maxLength={200} value={value.title} onChange={(e) => set('title', e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Bug preconditions</span>
          <textarea className={inputClass} maxLength={50000} value={preconditions} onChange={(e) => setPreconditions(e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Steps to reproduce, one per line</span>
          <textarea className={inputClass} required rows={3} maxLength={50000} value={steps} onChange={(e) => setSteps(e.target.value)} />
        </label>
        <ol className="list-decimal pl-4 text-xs text-muted">{lines(steps).map((v, i) => <li key={i}>{v}</li>)}</ol>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Bug expected result</span>
          <textarea className={inputClass} required maxLength={20000} value={value.expected_result} onChange={(e) => set('expected_result', e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Bug actual result</span>
          <textarea className={inputClass} required maxLength={20000} value={value.actual_result} onChange={(e) => set('actual_result', e.target.value)} />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Severity</span>
            <select className={inputClass} value={value.severity} onChange={(e) => set('severity', e.target.value)}>
              {['Critical', 'High', 'Medium', 'Low'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Bug priority</span>
            <select className={inputClass} value={value.priority} onChange={(e) => set('priority', e.target.value)}>
              {['High', 'Medium', 'Low'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Bug environment</span>
            <input className={inputClass} required maxLength={200} value={value.environment} onChange={(e) => set('environment', e.target.value)} />
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Bug build / version</span>
            <input className={inputClass} required maxLength={200} value={value.build} onChange={(e) => set('build', e.target.value)} />
          </label>
        </div>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Bug evidence reference (optional)</span>
          <input className={inputClass} maxLength={2000} value={value.evidence_reference} onChange={(e) => set('evidence_reference', e.target.value)} />
        </label>
        <button type="submit" className={buttonPrimaryClass}>Save bug</button>
      </fieldset>
    </form>
  );
}

function BugDetail({ initial, canManage, changed, refresh }) {
  const [data, setData] = useState(null);
  const [events, setEvents] = useState(null);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(false);
  const [target, setTarget] = useState('');
  const [retest, setRetest] = useState('');
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const lock = useRef(false);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setLoading(true);
    Promise.all([
      apiFetch(`/api/bugs/${initial.id}`, { signal: controller.signal }),
      apiFetch(`/api/bugs/${initial.id}/history?page=${page}`, { signal: controller.signal }),
    ])
      .then(async (responses) => {
        const results = await Promise.all(responses.map((r) => r.json()));
        if (responses.some((r) => !r.ok)) throw new Error(results.find((r) => r.error)?.error || 'Unable to load bug.');
        if (!controller.signal.aborted) {
          setData(results[0]);
          setEvents(results[1]);
          setTarget(({ Open: 'In Progress', 'In Progress': 'Ready for Retest', 'Ready for Retest': 'Closed', Closed: 'Open' })[results[0].bug.status]);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [initial.id, initial.revision, page, version, refresh]);

  async function save(payload, status = false) {
    if (lock.current || loading || !data) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      const response = await apiFetch(`/api/bugs/${initial.id}${status ? '/status' : ''}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, revision: data.bug.revision }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to save bug.');
      setData((old) => ({ ...old, bug: result.bug }));
      setEditing(false);
      setRetest('');
      setReason('');
      setNote('');
      setVersion((v) => v + 1);
      changed();
    } catch (e) {
      setError(e.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  if (!data) return error ? <p className="text-xs text-danger" role="alert">{error}</p> : <p className="text-xs text-muted">Loading bug details…</p>;
  const b = data.bug;
  const targets = ({ Open: ['In Progress'], 'In Progress': ['Ready for Retest'], 'Ready for Retest': ['Closed', 'Open'], Closed: ['Open'] })[b.status];

  return (
    <section className="bug-detail mt-3 space-y-3 border-t border-line pt-3 text-xs">
      <p className="text-muted">
        Project {b.project_id} · <a className="text-accent hover:underline" href={`#requirement/${b.requirement_id}`}>REQ-{b.requirement_id}</a> ·{' '}
        <a className="text-accent hover:underline" href={`#requirement/${b.requirement_id}`} onClick={(e) => showSource(e, `test-case-${b.scenario_id}`)}>TC-{b.scenario_id}</a> ·{' '}
        <a className="text-accent hover:underline" href={`#requirement/${b.requirement_id}`} onClick={(e) => showSource(e, `execution-${b.failed_execution_id}`)}>Failed execution #{b.failed_execution_id}</a>
      </p>
      <p className="text-muted">
        Reported by {b.reporter_name} (User {b.reporter_id}), {new Date(b.created_at).toLocaleString()}. Updated {new Date(b.updated_at).toLocaleString()}.
      </p>
      <p><strong className="text-ink">Preconditions:</strong> {b.preconditions.join('; ') || 'None'}</p>
      <ol className="list-decimal pl-4 space-y-0.5 text-ink">{b.steps_to_reproduce.map((v, i) => <li key={i}>{v}</li>)}</ol>
      <p><strong className="text-ink">Expected:</strong> {b.expected_result}</p>
      <p><strong className="text-ink">Actual:</strong> {b.actual_result}</p>
      <p><strong className="text-ink">Environment:</strong> {b.environment}; <strong className="text-ink">Build:</strong> {b.build}</p>
      <p><strong className="text-ink">Evidence reference:</strong> {b.evidence_reference || 'None'}</p>
      {b.last_retest_execution_id && <p>Linked retest execution #{b.last_retest_execution_id}</p>}
      {b.resolution_reason && <p>Documented resolution: {b.resolution_reason}</p>}
      {error && <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-danger" role="alert">{error}</p>}
      {loading && <p className="text-muted" role="status">Refreshing current bug revision…</p>}

      {canManage && (
        <div className="space-y-3">
          <button type="button" className={buttonSecondaryClass} disabled={busy || loading} onClick={() => setEditing((v) => !v)}>
            {editing ? 'Cancel edit' : 'Edit bug'}
          </button>
          {editing && <BugForm key={b.revision} initial={b} busy={busy || loading} save={(value) => save(value)} label={`Edit ${b.stable_id}`} />}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              save({ status: target, retest_execution_id: retest ? Number(retest) : null, resolution_reason: reason, note }, true);
            }}
            className="rounded-xl border border-line bg-surface-alt/40 p-3 space-y-2.5"
          >
            <fieldset disabled={busy || loading} className="space-y-2.5">
              <legend className="font-semibold text-ink">Bug status</legend>
              <p className="text-[11px] text-muted">
                Open → In Progress → Ready for Retest → Closed. Reopen with a new failed retest.
              </p>
              <label className="block space-y-1 font-medium text-ink">
                <span>Next bug status</span>
                <select className={inputClass} value={target} onChange={(e) => setTarget(e.target.value)}>
                  {targets.map((v) => <option key={v}>{v}</option>)}
                </select>
              </label>
              {['Closed', 'Open'].includes(target) && (
                <>
                  <label className="block space-y-1 font-medium text-ink">
                    <span>Retest execution ID</span>
                    <input className={inputClass} type="number" min={1} list={`bug-retests-${b.id}`} required={target === 'Open'} value={retest} onChange={(e) => setRetest(e.target.value)} />
                  </label>
                  <datalist id={`bug-retests-${b.id}`}>
                    {data.retests.map((v) => <option key={v.id} value={v.id}>{v.status} · {v.environment} · {v.build}</option>)}
                  </datalist>
                  <p className="text-[11px] text-muted">
                    Recent retests: {data.retests.map((v) => `#${v.id} ${v.status} (${v.build})`).join('; ') || 'None. Record a separate Manual execution first.'}
                  </p>
                  {target === 'Closed' && (
                    <label className="block space-y-1 font-medium text-ink">
                      <span>Resolution reason (required without a passing retest)</span>
                      <textarea className={inputClass} required={!retest} maxLength={5000} value={reason} onChange={(e) => setReason(e.target.value)} />
                    </label>
                  )}
                </>
              )}
              <label className="block space-y-1 font-medium text-ink">
                <span>Status-change note</span>
                <textarea className={inputClass} maxLength={5000} value={note} onChange={(e) => setNote(e.target.value)} />
              </label>
              <button type="submit" className={buttonPrimaryClass}>Save bug status</button>
            </fieldset>
          </form>
        </div>
      )}

      {events && (
        <section className="space-y-2 border-t border-line pt-3">
          <h5 className="font-semibold text-ink">Status and change history</h5>
          <ol className="space-y-2">
            {events.history.map((event) => (
              <li key={event.id} className="rounded-lg border border-line bg-surface p-2.5 space-y-1">
                <p className="font-medium text-ink">
                  {event.action}: {event.from_status || 'Created'} → {event.to_status} · {event.actor_name} · {new Date(event.recorded_at).toLocaleString()}
                </p>
                {event.note && <p className="text-muted">{event.note}</p>}
                {event.retest_execution_id && <p className="text-muted">Retest execution #{event.retest_execution_id}</p>}
                <details>
                  <summary className="cursor-pointer text-[11px] text-accent">Recorded bug revision {event.snapshot.revision}</summary>
                  <p className="mt-1 text-muted">{event.snapshot.title} · Severity {event.snapshot.severity} · Priority {event.snapshot.priority}</p>
                  {event.snapshot.resolution_reason && <p className="text-muted">{event.snapshot.resolution_reason}</p>}
                </details>
              </li>
            ))}
          </ol>
          <div className="flex gap-2">
            <button type="button" className={buttonSecondaryClass} disabled={page === 1} onClick={() => setPage((v) => v - 1)}>Previous bug history</button>
            <button type="button" className={buttonSecondaryClass} disabled={page * events.page_size >= events.total} onClick={() => setPage((v) => v + 1)}>Next bug history</button>
          </div>
        </section>
      )}
    </section>
  );
}

export default function ExecutionBugs({ execution, user, refresh }) {
  const [data, setData] = useState(null);
  const [creating, setCreating] = useState(false);
  const [opened, setOpened] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const lock = useRef(false);
  const submission = useRef(null);
  const canManage = user?.role === 'admin' || (user?.role === 'SQA Engineer' && user.permissions?.includes('manage_bugs'));

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    apiFetch(`/api/executions/${execution.id}/bugs`, { signal: controller.signal })
      .then(async (response) => {
        const value = await response.json();
        if (!response.ok) throw new Error(value.error || 'Unable to load linked bugs.');
        if (!controller.signal.aborted) setData(value);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [execution.id, refresh, version]);

  async function create(value) {
    if (lock.current) return;
    const body = JSON.stringify(value);
    if (submission.current?.body !== body) submission.current = { body, key: crypto.randomUUID() };
    lock.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const response = await apiFetch(`/api/executions/${execution.id}/bugs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': submission.current.key },
        body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to save bug.');
      setCreating(false);
      setOpened(result.bug.id);
      setVersion((v) => v + 1);
      setNotice(result.created ? 'Bug saved.' : 'An identical linked bug already exists; no duplicate was created.');
    } catch (e) {
      setError(e.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <section className="execution-bugs mt-3 rounded-xl border border-line bg-surface p-4 space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-danger">Bugs linked to failed execution #{execution.id}</h4>
      {error && <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
      {notice && <p className="rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">{notice}</p>}
      {data && (
        <div className="space-y-3">
          <p className="text-xs text-muted">{data.bugs.length} linked bugs. Review existing bugs before reporting another.</p>
          {data.bugs.map((b) => (
            <article className="card rounded-xl border border-line bg-surface-alt/40 p-3 space-y-2" key={b.id}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h5 className="text-xs font-semibold text-ink">{b.stable_id}: {b.title}</h5>
                <div className="flex items-center gap-1.5">
                  <StatusBadge value={b.status} />
                  <StatusBadge value={b.severity} />
                  <StatusBadge value={b.priority} />
                </div>
              </div>
              <button type="button" className={buttonSecondaryClass} onClick={() => setOpened(opened === b.id ? null : b.id)}>
                {opened === b.id ? 'Close' : 'Open'} {b.stable_id}
              </button>
              {opened === b.id && <BugDetail initial={b} canManage={canManage} refresh={refresh} changed={() => setVersion((v) => v + 1)} />}
            </article>
          ))}
          {canManage && data.prefill && (
            <div className="space-y-3">
              <button type="button" className={buttonPrimaryClass} disabled={busy} onClick={() => setCreating(true)}>
                Create bug from failed execution
              </button>
              {creating && <BugForm initial={data.prefill} busy={busy} save={create} label="Review failure details before creating bug" />}
            </div>
          )}
          {!canManage && <p className="text-xs text-muted">Read-only bug access. SQA Engineers and SQA Admins manage bug reports.</p>}
        </div>
      )}
    </section>
  );
}
