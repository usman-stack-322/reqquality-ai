import React, { useEffect, useRef, useState } from 'react';
import { Plus, Sparkles } from 'lucide-react';
import { apiFetch } from '../api.js';
import ExecutionBugs from './ExecutionBugs';
import AIReviewAssistant from './AIReviewAssistant';
import { StatusBadge, buttonPrimaryClass, buttonSecondaryClass, buttonSoftAccentClass, inputClass } from './ui';

const blank = {
  title: '',
  category: 'Positive',
  preconditions: [],
  test_data: '',
  test_steps: [],
  expected_result: '',
  test_type: 'Unspecified',
  priority: 'Medium',
  criterion_codes: [],
  clarification_notes: '',
};
const split = (value) => value.split('\n').map((v) => v.trim()).filter(Boolean);

function CaseForm({ value: initial, requirement, onSave, busy }) {
  const [value, setValue] = useState(initial);
  const [preconditions, setPreconditions] = useState(initial.preconditions.join('\n'));
  const [steps, setSteps] = useState(initial.test_steps.join('\n'));
  const set = (key, entry) => setValue((v) => ({ ...v, [key]: entry }));

  return (
    <form
      className="case-edit-form rounded-xl border border-line bg-surface-alt/40 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ ...value, preconditions: split(preconditions), test_steps: split(steps) });
      }}
    >
      <fieldset disabled={busy} className="space-y-3">
        <legend className="text-xs font-semibold uppercase tracking-wider text-accent">
          {initial.id ? `Edit TC-${initial.id}` : 'Create detailed test case'}
        </legend>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Case title</span>
          <input className={inputClass} required maxLength={200} value={value.title} onChange={(e) => set('title', e.target.value)} />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Case category</span>
            <select className={inputClass} value={value.category} onChange={(e) => set('category', e.target.value)}>
              {['Positive', 'Negative', 'Boundary', 'Edge-case'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Test type</span>
            <select className={inputClass} value={value.test_type} onChange={(e) => set('test_type', e.target.value)}>
              {['Unspecified', 'Functional', 'Security', 'Performance', 'Usability', 'Regression', 'Other'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Case priority</span>
            <select className={inputClass} value={value.priority} onChange={(e) => set('priority', e.target.value)}>
              {['Low', 'Medium', 'High'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </label>
        </div>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Preconditions, one per line</span>
          <textarea className={inputClass} maxLength={50000} value={preconditions} onChange={(e) => setPreconditions(e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Test data</span>
          <textarea className={inputClass} maxLength={10000} value={value.test_data} onChange={(e) => set('test_data', e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Execution steps, one per line</span>
          <textarea className={inputClass} required rows={4} maxLength={50000} value={steps} onChange={(e) => setSteps(e.target.value)} />
        </label>
        <ol className="list-decimal pl-4 text-xs text-muted" aria-label="Numbered execution steps">
          {split(steps).map((v, i) => <li key={i}>{v}</li>)}
        </ol>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Expected results</span>
          <textarea className={inputClass} required rows={3} maxLength={10000} value={value.expected_result} onChange={(e) => set('expected_result', e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Clarification needs</span>
          <textarea className={inputClass} maxLength={5000} value={value.clarification_notes} onChange={(e) => set('clarification_notes', e.target.value)} />
        </label>
        <fieldset className="space-y-1.5 rounded-lg border border-line bg-surface p-3">
          <legend className="px-1 text-xs font-semibold text-ink">Acceptance-criteria links for current requirement version</legend>
          {requirement.acceptance_criteria.map((c) => (
            <label key={c.criterion_code} className="flex items-start gap-2 text-xs text-ink cursor-pointer">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={value.criterion_codes.includes(c.criterion_code)}
                onChange={(e) =>
                  set(
                    'criterion_codes',
                    e.target.checked ? [...value.criterion_codes, c.criterion_code] : value.criterion_codes.filter((v) => v !== c.criterion_code),
                  )
                }
              />
              <span><strong>{c.criterion_code}:</strong> {c.description}</span>
            </label>
          ))}
        </fieldset>
        {value.criterion_codes
          .filter((code) => !requirement.acceptance_criteria.some((c) => c.criterion_code === code))
          .map((code) => (
            <label key={code} className="flex items-center gap-2 text-xs text-warning">
              <input type="checkbox" checked onChange={() => set('criterion_codes', value.criterion_codes.filter((v) => v !== code))} />
              {code}: historical link; remove or replace before rebasing
            </label>
          ))}
        <p className="text-[11px] text-muted">
          Saving creates a new Draft case version linked to requirement content version {requirement.content_revision}.
        </p>
        <button type="submit" className={buttonPrimaryClass}>Save test case as Draft</button>
      </fieldset>
    </form>
  );
}

function CaseReview({ testCase: c, requirement, busy, send }) {
  const [target, setTarget] = useState(c.review_status === 'In Review' ? 'Approved' : 'In Review');
  const [notes, setNotes] = useState(c.review_notes || '');
  if (c.review_status === 'Approved') {
    return <p className="text-xs text-success">This case is approved. Editing it creates a new Draft version.</p>;
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send(`/${c.id}/review`, 'PATCH', { revision: requirement.revision, case_revision: c.case_revision, review_status: target, review_notes: notes });
      }}
      className="rounded-lg border border-line bg-surface-alt/50 p-3"
    >
      <fieldset disabled={busy} className="space-y-2.5">
        <legend className="text-xs font-semibold text-ink">Test case review</legend>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Case review decision</span>
          <select className={inputClass} value={target} onChange={(e) => setTarget(e.target.value)}>
            {(c.review_status === 'In Review' ? ['Approved', 'Needs Revision', 'In Review'] : ['In Review']).map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Case reviewer notes</span>
          <textarea className={inputClass} required={target === 'Needs Revision'} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
        <button type="submit" className={buttonPrimaryClass}>Save case review</button>
      </fieldset>
    </form>
  );
}

function ExecutionForm({ testCase, onSave, busy }) {
  const [value, setValue] = useState({ status: 'Not Run', actual_result: '', blocked_reason: '', environment: '', build: '', notes: '', evidence_reference: '' });
  const submission = useRef(null);
  const set = (key, entry) => setValue((v) => ({ ...v, [key]: entry }));

  return (
    <form
      className="manual-execution-form mt-3 rounded-xl border border-line bg-surface-alt/40 p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const payload = { ...value, case_revision: testCase.case_revision };
        const body = JSON.stringify(payload);
        if (submission.current?.body !== body) submission.current = { body, key: crypto.randomUUID() };
        if (await onSave(payload, submission.current.key)) {
          submission.current = null;
          setValue((v) => ({ ...v, status: 'Not Run', actual_result: '', blocked_reason: '', notes: '', evidence_reference: '' }));
        }
      }}
    >
      <fieldset disabled={busy} className="space-y-3">
        <legend className="text-xs font-semibold uppercase tracking-wider text-accent">Manual execution</legend>
        <p className="text-xs text-muted">
          You run these steps against your application and record the observed result. Generating or saving this case does not test an external application.
        </p>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Execution status</span>
          <select className={inputClass} value={value.status} onChange={(e) => set('status', e.target.value)}>
            {['Not Run', 'Pass', 'Fail', 'Blocked'].map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Actual result</span>
          <textarea className={inputClass} required={['Pass', 'Fail'].includes(value.status)} maxLength={20000} value={value.actual_result} onChange={(e) => set('actual_result', e.target.value)} />
        </label>
        {value.status === 'Blocked' && (
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Blocked reason</span>
            <textarea className={inputClass} required maxLength={5000} value={value.blocked_reason} onChange={(e) => set('blocked_reason', e.target.value)} />
          </label>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Environment</span>
            <input className={inputClass} required maxLength={200} value={value.environment} onChange={(e) => set('environment', e.target.value)} />
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Build / version</span>
            <input className={inputClass} required maxLength={200} value={value.build} onChange={(e) => set('build', e.target.value)} />
          </label>
        </div>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Execution notes</span>
          <textarea className={inputClass} maxLength={10000} value={value.notes} onChange={(e) => set('notes', e.target.value)} />
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Evidence reference (optional)</span>
          <input className={inputClass} maxLength={2000} value={value.evidence_reference} onChange={(e) => set('evidence_reference', e.target.value)} />
        </label>
        <button type="submit" className={buttonPrimaryClass}>Record manual execution / retest</button>
      </fieldset>
    </form>
  );
}

function History({ rid, testCase, refresh, user }) {
  const [bugExecution, setBugExecution] = useState(null);
  const [tab, setTab] = useState('executions');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setData(null);
    apiFetch(`/api/requirements/${rid}/test-cases/${testCase.id}/${tab}?page=${page}`, { signal: controller.signal })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Unable to load history.');
        if (!controller.signal.aborted) setData(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [rid, testCase.id, tab, page, refresh]);

  return (
    <section className="mt-3 space-y-3 border-t border-line pt-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold text-ink">Historical records</h4>
        <div className="flex gap-1.5">
          <button type="button" className={tab === 'executions' ? buttonPrimaryClass : buttonSecondaryClass} onClick={() => { setTab('executions'); setPage(1); }}>
            Manual execution history
          </button>
          <button type="button" className={tab === 'versions' ? buttonPrimaryClass : buttonSecondaryClass} onClick={() => { setTab('versions'); setPage(1); }}>
            Case version history
          </button>
        </div>
      </div>
      {error && <p className="text-danger" role="alert">{error}</p>}
      {data && (
        <div className="space-y-2">
          <p className="text-muted">{data.total} {tab} recorded</p>
          {data[tab].map((item) => (
            <details key={item.id} id={tab === 'executions' ? `execution-${item.id}` : undefined} className="rounded-lg border border-line bg-surface p-3">
              <summary className="cursor-pointer font-semibold text-ink">
                {tab === 'executions'
                  ? `Execution #${item.id}: ${item.status} — ${item.tester_name}, ${new Date(item.executed_at).toLocaleString()}`
                  : `Case version ${item.case_revision} — ${new Date(item.recorded_at).toLocaleString()}`}
              </summary>
              <div className="mt-2 space-y-1.5 text-muted">
                {tab === 'executions' && (
                  <>
                    <p>Environment: {item.environment}; Build: {item.build}</p>
                    <p>Actual result: {item.actual_result || 'Not recorded'}</p>
                    {item.blocked_reason && <p>Blocked: {item.blocked_reason}</p>}
                    <p>Notes: {item.notes || 'None'}</p>
                    <p>Evidence reference: {item.evidence_reference || 'None'}</p>
                  </>
                )}
                {tab === 'executions' && item.status === 'Fail' && (
                  <div>
                    <button type="button" className={buttonSecondaryClass} onClick={() => setBugExecution(bugExecution === item.id ? null : item.id)}>
                      Bugs for execution #{item.id}
                    </button>
                    {bugExecution === item.id && <ExecutionBugs execution={item} user={user} refresh={refresh} />}
                  </div>
                )}
                <p>Project {item.snapshot.project_id} · Requirement content version {item.snapshot.requirement_revision} · Case version {item.snapshot.case_revision}</p>
                <p>Requirement: {item.snapshot.requirement_snapshot.description}</p>
                <p>Case: {item.snapshot.title}</p>
                <ol className="list-decimal pl-4 text-ink">{item.snapshot.test_steps.map((v, i) => <li key={i}>{v}</li>)}</ol>
                <p className="text-ink">Expected: {item.snapshot.expected_result}</p>
              </div>
            </details>
          ))}
          <div className="flex gap-2">
            <button type="button" className={buttonSecondaryClass} disabled={page === 1} onClick={() => setPage((v) => v - 1)}>Previous history page</button>
            <button type="button" className={buttonSecondaryClass} disabled={page * data.page_size >= data.total} onClick={() => setPage((v) => v + 1)}>Next history page</button>
          </div>
        </div>
      )}
    </section>
  );
}

export default function TestCases({ requirement: r, user, onUpdate, onRequestRevision }) {
  const [selected, setSelected] = useState([]);
  const [reviewContext, setReviewContext] = useState(null);
  const canRequest = (user?.role === 'Analyst' && user.permissions?.includes('create_requirements')) || (user?.role === 'SQA Engineer' && user.permissions?.includes('review_requirements'));
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState(null);
  const [opened, setOpened] = useState(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const canEdit = user?.role === 'SQA Engineer' && user.id !== r.created_by_user_id && user.permissions?.includes('review_requirements');
  const canExecute = user?.role === 'SQA Engineer' && user.permissions?.includes('execute_test_cases');

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    apiFetch(`/api/requirements/${r.id}/test-cases?page=${page}`, { signal: controller.signal })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Unable to load test cases.');
        if (!controller.signal.aborted) setData(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [r.id, r.revision, page, refresh]);

  async function send(path, method, payload, key) {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (key) headers['Idempotency-Key'] = key;
      const response = await apiFetch(`/api/requirements/${r.id}/test-cases${path}`, { method, headers, body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to save.');
      if (result.requirement) {
        setData(null);
        onUpdate(result.requirement);
      }
      setEditing(null);
      setRefresh((v) => v + 1);
      setNotice(result.execution ? 'Manual execution recorded. Earlier evidence is preserved.' : 'Case version saved.');
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function triggerAI(ids) {
    if (onRequestRevision) onRequestRevision(ids);
    else setReviewContext(ids);
  }

  return (
    <section className="detail-section detailed-test-cases rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4" aria-busy={busy}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">Detailed test cases &amp; Manual execution</h2>
          <p className="mt-0.5 text-xs text-muted">
            Project {r.project_id} · Requirement content version {r.content_revision}. AI-generated cases start as editable drafts.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <button type="button" className={buttonPrimaryClass} disabled={busy} onClick={() => setEditing({ ...blank, priority: r.user_priority || 'Medium' })}>
              <Plus className="size-3.5" aria-hidden="true" />
              Create test case
            </button>
          )}
        </div>
      </div>

      {canRequest && (
        <div className="ai-actions flex flex-wrap gap-2">
          <button type="button" className={buttonSoftAccentClass} onClick={() => triggerAI([])}>
            <Sparkles className="size-3.5" aria-hidden="true" />
            Discuss requirement coverage
          </button>
          <button type="button" className={buttonSecondaryClass} disabled={!selected.length} onClick={() => triggerAI([...selected])}>
            Request AI Revision for selected ({selected.length})
          </button>
        </div>
      )}

      {reviewContext && !onRequestRevision && (
        <AIReviewAssistant
          key={`${r.id}-${reviewContext.join(',')}`}
          requirement={r}
          caseIds={reviewContext}
          user={user}
          onUpdate={(updated) => {
            setData(null);
            onUpdate(updated);
          }}
          onClose={() => setReviewContext(null)}
        />
      )}

      {error && <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
      {notice && <p className="rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">{notice}</p>}
      {!data && !error && <p className="text-xs text-muted" role="status">Loading current test-case revisions…</p>}
      {error && <button type="button" className={buttonSecondaryClass} disabled={busy} onClick={() => setRefresh((v) => v + 1)}>Retry test cases</button>}

      {editing && (
        <CaseForm
          key={`${editing.id || 'new'}-${editing.case_revision || 0}`}
          value={editing}
          requirement={r}
          busy={busy}
          onSave={(value) => send(value.id ? `/${value.id}` : '', value.id ? 'PATCH' : 'POST', { ...value, revision: r.revision })}
        />
      )}

      <div className="space-y-3">
        {data?.test_cases.map((c) => (
          <article className="card rounded-xl border border-line bg-surface-alt/30 p-4 space-y-3" key={c.id} id={`test-case-${c.id}`}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-ink">{c.stable_id}: {c.title}</h3>
                <p className="text-xs text-muted">
                  {c.scenario_code} · {c.category} · {c.test_type} · Case v{c.case_revision} · Req v{c.requirement_revision}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <StatusBadge value={c.priority} />
                <StatusBadge value={c.review_status} />
                <StatusBadge value={c.latest_execution_status} />
              </div>
            </div>

            {canRequest && !c.archived && !c.stale && (
              <div className="ai-actions flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface p-2.5 text-xs">
                <label className="flex items-center gap-2 text-ink cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.includes(c.id)}
                    onChange={(e) => setSelected((v) => (e.target.checked ? [...v, c.id] : v.filter((id) => id !== c.id)))}
                  />
                  Select {c.stable_id} for shared feedback
                </label>
                <button type="button" className={buttonSoftAccentClass} onClick={() => triggerAI([c.id])}>
                  <Sparkles className="size-3" aria-hidden="true" />
                  Request AI Revision
                </button>
              </div>
            )}

            {c.archived && <p className="text-xs text-muted">Archived after reanalysis. Original links and execution evidence remain available below.</p>}
            {c.stale && !c.archived && <p className="text-xs text-warning">Earlier requirement version. Edit and verify the links to rebase this case before new execution.</p>}
            {c.needs_confirmation && <p className="text-xs text-warning">Draft/review needed; generated expected behavior is unconfirmed.</p>}
            {c.clarification_notes && <p className="rounded-lg border border-warning/30 bg-warning-tint px-3 py-1.5 text-xs text-warning">Requires clarification: {c.clarification_notes}</p>}

            <div className="space-y-1.5 text-xs">
              <p><strong className="text-ink">Criterion links:</strong> <span className="text-muted">{c.criterion_codes.join(', ') || 'None'}</span></p>
              <p><strong className="text-ink">Preconditions:</strong> <span className="text-muted">{c.preconditions.join('; ') || 'None'}</span></p>
              <p><strong className="text-ink">Test data:</strong> <span className="text-muted">{c.test_data || 'Not specified'}</span></p>
              <ol className="list-decimal pl-4 space-y-0.5 text-ink">{c.test_steps.map((v, i) => <li key={i}>{v}</li>)}</ol>
              <p><strong className="text-ink">Expected results:</strong> <span className="text-ink">{c.expected_result}</span></p>
            </div>

            {canEdit && !c.archived && (
              <div className="space-y-2 border-t border-line pt-2.5">
                <button type="button" className={buttonSecondaryClass} disabled={busy} onClick={() => setEditing(c)}>Edit {c.stable_id}</button>
                <CaseReview key={c.case_revision} testCase={c} requirement={r} busy={busy} send={send} />
              </div>
            )}

            <button type="button" className={buttonSecondaryClass} onClick={() => setOpened(opened === c.id ? null : c.id)}>
              {opened === c.id ? 'Close' : 'Open'} Manual execution and history for {c.stable_id}
            </button>

            {opened === c.id && (
              <>
                {canExecute && !c.archived && !c.stale && (
                  <ExecutionForm testCase={c} busy={busy} onSave={(payload, key) => send(`/${c.id}/executions`, 'POST', payload, key)} />
                )}
                <History rid={r.id} testCase={c} refresh={refresh} user={user} />
              </>
            )}
          </article>
        ))}
      </div>

      {data && (
        <nav className="flex items-center justify-between gap-2 border-t border-line pt-3 text-xs" aria-label="Test case pages">
          <button type="button" className={buttonSecondaryClass} disabled={page === 1} onClick={() => setPage((v) => v - 1)}>Previous cases</button>
          <span className="text-muted tabular-nums">Page {page}; {data.total} cases including archived</span>
          <button type="button" className={buttonSecondaryClass} disabled={page * data.page_size >= data.total} onClick={() => setPage((v) => v + 1)}>Next cases</button>
        </nav>
      )}
    </section>
  );
}
