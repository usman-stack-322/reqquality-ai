import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api.js';
import { GeminiErrorBanner, StatusBadge, buttonPrimaryClass, buttonSecondaryClass, inputClass } from './ui';

const fields = [
  'title',
  'category',
  'test_type',
  'priority',
  'preconditions',
  'test_data',
  'test_steps',
  'expected_result',
  'criterion_codes',
  'clarification_notes',
];
const display = (v) => (Array.isArray(v) ? v.join('\n') : v || 'None');

export function ProposalPreview({ turn }) {
  return (
    <div className="space-y-3">
      {turn.proposal.changes.map((change, i) => {
        const saved = turn.base_snapshot.test_cases.find((c) => c.id === change.case_id);
        return (
          <article className="ai-proposal rounded-xl border border-line bg-surface p-4 space-y-3" key={i}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-ink">
                {change.operation === 'new'
                  ? 'NEW proposed test case'
                  : `${change.operation === 'archive' ? 'Archive duplicate' : 'Revise'} TC-${change.case_id}`}
              </h4>
              <StatusBadge value={change.operation === 'archive' ? 'Archived' : 'Pending Review'} />
            </div>
            <p className="text-xs text-muted">{change.summary}</p>
            {change.operation === 'archive' && (
              <p className="rounded-lg border border-warning/25 bg-warning-tint px-3 py-1.5 text-xs text-warning">
                Acceptance archives this duplicate and preserves its history.
              </p>
            )}
            <div className="ai-comparison grid grid-cols-1 gap-3 md:grid-cols-2">
              <section className="rounded-lg border border-line bg-surface-alt/60 p-3 space-y-2 min-w-0">
                <h5 className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Saved version{saved ? ` · v${saved.case_revision}` : ''}
                </h5>
                {saved ? (
                  fields.map((k) => (
                    <div key={k} className="text-xs space-y-0.5">
                      <strong className="block text-[11px] font-semibold uppercase text-muted">
                        {k.replaceAll('_', ' ')}
                      </strong>
                      <pre className="whitespace-pre-wrap break-words font-sans text-ink">{display(saved[k])}</pre>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted">New case; no saved version.</p>
                )}
              </section>

              <section className="rounded-lg border border-accent/30 bg-surface p-3 space-y-2 min-w-0">
                <h5 className="text-xs font-semibold uppercase tracking-wider text-accent">
                  Proposed version · {change.operation === 'archive' ? 'Archived' : 'Pending Review on acceptance'}
                </h5>
                {fields.map((k) => {
                  const changed = JSON.stringify(saved?.[k]) !== JSON.stringify(change.content[k]);
                  return (
                    <div className={`${changed ? 'ai-changed ' : ''}text-xs space-y-0.5 py-0.5`} key={k}>
                      <strong className="block text-[11px] font-semibold uppercase text-muted">
                        {k.replaceAll('_', ' ')}
                        {changed ? ' · changed' : ''}
                      </strong>
                      <pre className="whitespace-pre-wrap break-words font-sans text-ink">{display(change.content[k])}</pre>
                    </div>
                  );
                })}
              </section>
            </div>
          </article>
        );
      })}
    </div>
  );
}

export default function AIReviewAssistant({ requirement, caseIds, user, onUpdate, onClose, inline = false }) {
  const [session, setSession] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  const lock = useRef(false);
  const submission = useRef(null);
  const active = useRef(true);
  const input = useRef(null);
  const base = `/api/requirements/${requirement.id}/ai-review`;

  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    apiFetch(base, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_ids: caseIds }),
      signal: controller.signal,
    })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) {
          const err = new Error(data.error || 'Unable to open review context.');
          err.code = data.code || '';
          throw err;
        }
        if (!controller.signal.aborted) {
          setSession(data);
          setError('');
          setErrorCode('');
          const failed = data.turns.filter((t) => ['failed', 'generating'].includes(t.status)).at(-1);
          if (failed) {
            setFeedback(failed.feedback);
            submission.current = { feedback: failed.feedback, key: failed.request_key };
          }
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e.message);
          setErrorCode(e.code || '');
        }
      });
    return () => {
      active.current = false;
      controller.abort();
    };
  }, [base, retry]);

  async function post(path, payload) {
    const r = await apiFetch(base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!r.ok) {
      const err = new Error(data.error || 'Unable to complete request.');
      err.code = data.code || '';
      throw err;
    }
    return data;
  }

  async function generate(e) {
    e?.preventDefault?.();
    if (lock.current || !feedback.trim() || !session) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setErrorCode('');
    setNotice('');
    if (submission.current?.feedback !== feedback) {
      submission.current = { feedback, key: crypto.randomUUID() };
    }
    try {
      const data = await post(`/${session.id}/messages`, {
        feedback,
        request_key: submission.current.key,
      });
      if (!active.current) return;
      setSession((s) => ({
        ...s,
        turns: [
          ...s.turns.filter((t) => t.id !== data.turn.id).map((t) => (t.status === 'proposed' ? { ...t, status: 'superseded' } : t)),
          data.turn,
        ],
      }));
      setFeedback('');
      submission.current = null;
      setNotice(data.turn.proposal.kind === 'proposal' ? 'Proposal ready. Saved cases are unchanged.' : 'Assistant response ready.');
    } catch (e) {
      if (active.current) {
        setError(e.message);
        setErrorCode(e.code || '');
      }
    } finally {
      lock.current = false;
      if (active.current) setBusy(false);
    }
  }

  async function decide(turn, action) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setErrorCode('');
    try {
      const data = await post(`/${session.id}/proposals/${turn.id}`, { action });
      if (!active.current) return;
      setSession((s) => ({
        ...s,
        turns: s.turns.map((t) => (t.id === turn.id ? { ...t, status: data.status } : t)),
      }));
      if (action === 'accept') onUpdate(data.requirement);
      setNotice(
        action === 'accept'
          ? 'Changes saved as Pending Review. SQA Engineer approval is still required.'
          : 'Proposal rejected. Saved cases are unchanged.',
      );
    } catch (e) {
      if (active.current) {
        setError(e.message);
        setErrorCode(e.code || '');
      }
    } finally {
      lock.current = false;
      if (active.current) setBusy(false);
    }
  }

  const canAccept =
    user.role === 'SQA Engineer' &&
    user.id !== requirement.created_by_user_id &&
    user.permissions?.includes('review_requirements');

  const wrapperClass = inline
    ? 'rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4'
    : 'ai-review-panel fixed inset-y-0 right-0 z-50 w-[min(900px,95vw)] overflow-y-auto border-l border-line bg-surface p-6 shadow-2xl space-y-4';

  const BodyTag = inline ? 'section' : 'aside';

  return (
    <BodyTag
      className={wrapperClass}
      role={inline ? undefined : 'dialog'}
      aria-labelledby="ai-review-title"
      aria-busy={busy}
    >
      <div className="space-y-2 border-b border-line pb-3">
        <header className="flex items-center justify-between gap-3">
          <h2 id="ai-review-title" className="text-base font-semibold text-ink">AI Review Assistant</h2>
          {onClose && (
            <button type="button" className={buttonSecondaryClass} onClick={onClose} aria-label="Close AI Review Assistant">
              Close
            </button>
          )}
        </header>
        <p className="text-xs font-medium text-ink">
          Project {requirement.project_id} · REQ-{requirement.id}: {requirement.title}
        </p>
        <p className="text-xs text-muted">
          Selected:{' '}
          {caseIds.length ? caseIds.map((id) => `TC-${id}`).join(', ') : 'Requirement coverage discussion (no cases selected)'}.
          Changing the selection opens its own conversation.
        </p>
      </div>

      <GeminiErrorBanner
        error={error}
        code={errorCode}
        busy={busy}
        onRetry={!session ? () => setRetry((v) => v + 1) : feedback.trim() ? () => generate() : undefined}
        retryLabel={!session ? 'Retry opening assistant' : 'Retry sending feedback'}
      />

      {notice && (
        <p className="rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">
          {notice}
        </p>
      )}

      {!session && !error && <p className="text-xs text-muted" role="status">Loading authorized review context…</p>}

      {session && (
        <div className="space-y-4">
          <p className="text-xs text-muted">
            Source content version {session.context.requirement.content_revision}. AI proposals need human review.
          </p>

          {!session.turns.length && (
            <p className="rounded-lg border border-dashed border-line bg-surface-alt/50 p-3 text-xs text-muted">
              Describe what needs improving, or ask about requirement coverage. Unsupported behavior will need clarification.
            </p>
          )}

          <div className="ai-conversation space-y-4" aria-label="Review conversation">
            {session.turns.map((t) => (
              <section key={t.id} className="ai-turn rounded-xl border border-line bg-surface-alt/30 p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Reviewer feedback</h3>
                  <StatusBadge value={t.status} />
                </div>
                <p className="ai-feedback whitespace-pre-wrap break-words text-sm text-ink">{t.feedback}</p>
                <small className="block text-[11px] text-muted">
                  {new Date(t.created_at).toLocaleString()} · {t.status}
                  {t.decision_actor_id ? ` · decision by user ${t.decision_actor_id}` : ''}
                </small>

                {t.proposal && (
                  <div className="space-y-3 border-t border-line pt-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-accent">Assistant</h3>
                    <p className="ai-feedback whitespace-pre-wrap break-words text-sm text-ink">{t.proposal.message}</p>
                    {t.status === 'proposed' ? (
                      <ProposalPreview turn={t} />
                    ) : (
                      t.proposal.changes.length > 0 && (
                        <details className="rounded-lg border border-line bg-surface p-3">
                          <summary className="cursor-pointer text-xs font-medium text-ink">View {t.status} proposal</summary>
                          <div className="mt-3"><ProposalPreview turn={t} /></div>
                        </details>
                      )
                    )}
                    {t.status === 'proposed' && (
                      <div className="ai-actions flex flex-wrap items-center gap-2 pt-1">
                        <button type="button" className={buttonPrimaryClass} disabled={busy || !canAccept} onClick={() => decide(t, 'accept')}>
                          Accept as Pending Review
                        </button>
                        <button type="button" className="inline-flex items-center justify-center rounded-lg border border-danger/35 bg-danger-tint px-3.5 py-2 text-xs font-semibold text-danger disabled:opacity-50" disabled={busy} onClick={() => decide(t, 'reject')}>
                          Reject
                        </button>
                        <button type="button" className={buttonSecondaryClass} disabled={busy} onClick={() => input.current?.focus()}>
                          Request Another Revision
                        </button>
                        {!canAccept && (
                          <p className="w-full text-[11px] text-muted">
                            An authorized SQA Engineer must accept revisions from their review context.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {t.status === 'failed' && (
                  <p className="rounded-lg border border-danger/25 bg-danger-tint px-3 py-2 text-xs text-danger">
                    Generation failed. Your feedback was saved; retry below.
                  </p>
                )}
                {t.status === 'generating' && (
                  <p className="rounded-lg border border-warning/25 bg-warning-tint px-3 py-2 text-xs text-warning">
                    A request is processing. Retry the same feedback if it was interrupted.
                  </p>
                )}
              </section>
            ))}
          </div>

          <form onSubmit={generate} className="space-y-3 border-t border-line pt-4">
            <label className="block space-y-1.5 text-xs font-semibold text-ink">
              <span>Feedback or coverage question</span>
              <textarea
                ref={input}
                className={inputClass}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                required
                maxLength={8000}
                rows={3}
                disabled={busy}
                placeholder="Ask Gemini to clarify edge cases, split missing criteria, or revise selected test cases…"
              />
            </label>
            <button type="submit" className={buttonPrimaryClass} disabled={busy || !feedback.trim()}>
              {busy ? 'Working…' : error ? 'Retry / Send feedback' : 'Send feedback'}
            </button>
          </form>
        </div>
      )}
    </BodyTag>
  );
}
