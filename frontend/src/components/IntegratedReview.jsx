import React, { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { apiFetch } from '../api.js';
import ExecutionBugs from './ExecutionBugs';
import { StatusBadge, buttonSecondaryClass, inputClass } from './ui';

export default function IntegratedReview({ requirement: r, user, initialData = null }) {
  const [data, setData] = useState(initialData);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(!initialData);
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState(initialData?.current_content_revision ?? null);
  const [bugsFor, setBugsFor] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    apiFetch(`/api/requirements/${r.id}/traceability`, { signal: controller.signal })
      .then(async (response) => {
        const value = await response.json();
        if (!response.ok) throw new Error(value.error || 'Unable to load versioned evidence.');
        if (!controller.signal.aborted) {
          setData(value);
          setSelected((old) => old ?? value.current_content_revision);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [r.id, r.revision, retry]);

  const version = data?.versions.find((v) => v.content_revision === selected);
  const cases = new Map();
  for (const v of data?.case_versions || []) if (v.requirement_revision === selected) cases.set(v.scenario_id, v);
  const runs = (data?.executions || []).filter((e) => e.requirement_revision === selected);
  const reviews = (data?.reviews || []).filter((v) => v.content_revision === selected);

  return (
    <section className="detail-section integrated-review rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4" aria-busy={loading}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Requirement versions, traceability &amp; SQA review</h2>
          <p className="mt-0.5 text-xs text-muted">
            Requirement version → criteria → case snapshot → Manual execution → bug → version-bound review.
          </p>
        </div>
        <button type="button" className={buttonSecondaryClass} disabled={loading} onClick={() => setRetry((v) => v + 1)}>
          <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
          Refresh evidence / Retry
        </button>
      </div>

      {loading && <p className="text-xs text-muted" role="status">Loading versioned evidence…</p>}
      {error && <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}

      {!loading && !error && data && (
        <div className="space-y-4 text-xs">
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface-alt/50 p-3">
            <span>Current SQA review:</span>
            <StatusBadge value={data.sqa_review_status} />
            <span className="text-muted">· Authoring: {data.authoring_status} · Version {data.current_content_revision}</span>
          </div>

          <label className="block space-y-1 font-medium text-ink">
            <span>Requirement version</span>
            <select
              className={inputClass}
              value={selected ?? ''}
              onChange={(e) => {
                setSelected(Number(e.target.value));
                setBugsFor(null);
              }}
            >
              {data.versions.map((v) => (
                <option key={v.id} value={v.content_revision}>
                  {v.content_revision}
                  {v.current ? ' (current)' : ' (historical)'}
                </option>
              ))}
            </select>
          </label>

          {version ? (
            <div className="space-y-3 rounded-lg border border-line bg-surface-alt/40 p-3">
              <p className="text-muted">
                {version.current ? 'Current source version.' : 'Historical evidence: this does not validate the current requirement.'}{' '}
                Recorded {new Date(version.recorded_at).toLocaleString()}. {version.origin}.
              </p>
              <p className="text-ink">{version.snapshot.description}</p>
              <h3 className="font-semibold text-ink">Acceptance criteria for version {selected}</h3>
              {version.snapshot.acceptance_criteria?.length ? (
                <ul className="space-y-1.5 list-disc pl-4">
                  {version.snapshot.acceptance_criteria.map((a) => (
                    <li key={a.criterion_code} className="text-ink">
                      <strong>{a.criterion_code}:</strong> {a.description}
                      {version.current && r.criteria_review_required ? <span className="ml-1 text-warning">— Needs review</span> : ''}
                      <ul className="mt-1 list-circle pl-4 text-muted">
                        {[...cases.values()]
                          .filter((v) => v.snapshot.criterion_codes.includes(a.criterion_code))
                          .map((v) => (
                            <li key={v.id}>TC-{v.scenario_id}, case revision {v.case_revision}, snapshot #{v.id}</li>
                          ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted">No acceptance criteria recorded for this version.</p>
              )}
            </div>
          ) : (
            <p className="text-muted">No source snapshot recorded. Earlier legacy versions may be unavailable.</p>
          )}

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-ink">Cases and immutable execution evidence</h3>
            {!cases.size && <p className="text-muted">No test-case snapshots for this version.</p>}
            {[...cases.values()].map((v) => (
              <details key={v.id} className="rounded-xl border border-line bg-surface-alt/30 p-3">
                <summary className="cursor-pointer font-semibold text-ink">
                  TC-{v.scenario_id}: {v.snapshot.title} — case revision {v.case_revision}, {v.snapshot.review_status}
                </summary>
                <div className="mt-2.5 space-y-2 text-muted">
                  <p>Criteria: {v.snapshot.criterion_codes.join(', ') || 'Unlinked'}. Case snapshot #{v.id}.</p>
                  <ol className="list-decimal pl-4 text-ink">{v.snapshot.test_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                  <p className="text-ink"><strong>Expected:</strong> {v.snapshot.expected_result}</p>
                  {runs.filter((e) => e.scenario_id === v.scenario_id).length === 0 && (
                    <p>Not Run. No execution recorded for this source version.</p>
                  )}
                  {runs
                    .filter((e) => e.scenario_id === v.scenario_id)
                    .map((e) => (
                      <article key={e.id} className="rounded-lg border border-line bg-surface p-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="font-semibold text-ink">Manual execution #{e.id}</h4>
                          <StatusBadge value={e.status} />
                        </div>
                        <p>Executed case snapshot #{e.case_version_id}; {e.tester_name}, {new Date(e.executed_at).toLocaleString()}. {e.environment} / {e.build}</p>
                        <p>Actual: {e.actual_result || 'Not recorded'}. Blocked reason: {e.blocked_reason || 'None'}</p>
                        <p>Evidence reference: {e.evidence_reference || 'None'}</p>
                        {data.bugs.filter((b) => b.failed_execution_id === e.id).length > 0 && (
                          <ul className="list-disc pl-4 text-danger">
                            {data.bugs
                              .filter((b) => b.failed_execution_id === e.id)
                              .map((b) => (
                                <li key={b.id}>{b.stable_id}: {b.title} — {b.status}, Severity {b.severity}, Priority {b.priority}</li>
                              ))}
                          </ul>
                        )}
                        {e.status === 'Fail' && (
                          <div>
                            <button type="button" className={buttonSecondaryClass} onClick={() => setBugsFor((old) => (old === e.id ? null : e.id))}>
                              Inspect / manage bugs for execution #{e.id}
                            </button>
                            {bugsFor === e.id && <ExecutionBugs execution={e} user={user} refresh={retry} />}
                          </div>
                        )}
                      </article>
                    ))}
                </div>
              </details>
            ))}
          </div>

          <div className="space-y-2 border-t border-line pt-3">
            <h3 className="text-sm font-semibold text-ink">SQA review of version {selected}</h3>
            {reviews.length ? (
              <ol className="space-y-2">
                {reviews.map((v) => (
                  <li key={v.id} className="rounded-lg border border-line bg-surface-alt/40 p-3 space-y-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge value={v.status} />
                      <span className="font-medium text-ink">{v.reviewer_name} (User {v.reviewer_id})</span>
                      <span className="text-muted">· {new Date(v.reviewed_at).toLocaleString()}</span>
                    </div>
                    <p className="text-ink">{v.notes || 'No notes recorded.'}</p>
                    <p className="text-[11px] text-muted">
                      Reviewed requirement version {v.content_revision}; case snapshots {v.snapshot.case_version_ids.join(', ') || 'none'}; executions {v.snapshot.execution_ids.join(', ') || 'none'}; bugs {v.snapshot.bug_ids.join(', ') || 'none'}.
                    </p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-muted">No version-verified SQA review. Legacy review metadata has an unknown reviewed version.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
