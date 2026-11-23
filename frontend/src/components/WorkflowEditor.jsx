import React, { useRef, useState } from 'react';
import { Sparkles, Save, Send } from 'lucide-react';
import { apiFetch } from '../api.js';
import AnalysisDraft from './AnalysisDraft';
import { GeminiErrorBanner, buttonPrimaryClass, buttonSecondaryClass, buttonSoftAccentClass, inputClass } from './ui';

export default function WorkflowEditor({ requirement: r, user, onUpdate }) {
  const [title, setTitle] = useState(r.title);
  const [description, setDescription] = useState(r.description);
  const [type, setType] = useState(r.requirement_type);
  const [priority, setPriority] = useState(r.user_priority || r.priority);
  const [criteria, setCriteria] = useState(r.acceptance_criteria.map((c) => c.description).join('\n'));
  const [answers, setAnswers] = useState(r.analysis_summary?.clarifications || '');
  const [suggestion, setSuggestion] = useState(r.analysis_draft || null);
  const [analysisEdits, setAnalysisEdits] = useState({});
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState('');

  const dirty =
    title !== r.title ||
    description !== r.description ||
    type !== r.requirement_type ||
    priority !== (r.user_priority || r.priority) ||
    criteria !== r.acceptance_criteria.map((c) => c.description).join('\n') ||
    answers !== (r.analysis_summary?.clarifications || '');

  async function send(url, method, data, analysis = false) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError('');
    setErrorCode('');
    try {
      const response = await apiFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, revision: r.revision }),
      });
      const result = await response.json();
      if (!response.ok) {
        const err = new Error(result.error || 'Unable to save. Retry after reloading the latest revision.');
        err.code = result.code || '';
        throw err;
      }
      if (analysis) {
        setSuggestion(result);
        setAnalysisEdits({});
      } else {
        onUpdate(result.requirement);
      }
    } catch (e) {
      setError(e.message);
      setErrorCode(e.code || '');
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  const canEdit = user?.role === 'Analyst' && user.permissions?.includes('create_requirements');
  if (!canEdit) return null;

  const analyzePayload = {
    title,
    description,
    requirement_type: type,
    priority,
    clarifications: answers,
    requirement_id: r.id,
    requirement_revision: r.revision,
  };

  return (
    <section className="detail-section workflow-editor rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4" aria-busy={busy}>
      <fieldset disabled={busy} className="space-y-4">
        <legend className="text-sm font-semibold text-ink">Prepare requirement for review</legend>

        <div className="rounded-lg border border-line bg-surface-alt/50 p-3 text-xs text-muted space-y-1">
          <p>
            <strong className="text-ink">Project context:</strong>{' '}
            {r.project?.context || 'No context supplied; missing values require clarification.'}
          </p>
          <p>
            <strong className="text-ink">Reviewer feedback:</strong> {r.reviewer_notes || 'No feedback yet.'}
          </p>
        </div>

        {r.analysis_outdated && (
          <p className="rounded-lg border border-warning/30 bg-warning-tint px-3 py-2 text-xs text-warning" role="status">
            Saved analysis is outdated for the current context or configuration. It remains historical evidence; analyze explicitly to update it.
          </p>
        )}

        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Title</span>
          <input
            className={inputClass}
            value={title}
            maxLength={200}
            onChange={(e) => {
              setTitle(e.target.value);
              setSuggestion(null);
            }}
          />
        </label>

        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Description</span>
          <textarea
            className={inputClass}
            rows={4}
            value={description}
            maxLength={20000}
            onChange={(e) => {
              setDescription(e.target.value);
              setSuggestion(null);
            }}
          />
        </label>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Type</span>
            <select
              className={inputClass}
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setSuggestion(null);
              }}
            >
              {['Functional', 'Non-Functional', 'Business'].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>

          <label className="block space-y-1 text-xs font-medium text-ink">
            <span>Priority</span>
            <select
              className={inputClass}
              value={priority}
              onChange={(e) => {
                setPriority(e.target.value);
                setSuggestion(null);
              }}
            >
              {['Low', 'Medium', 'High'].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Clarification answers</span>
          <textarea className={inputClass} rows={3} value={answers} maxLength={20000} onChange={(e) => setAnswers(e.target.value)} />
        </label>

        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Acceptance criteria, one per line</span>
          <textarea className={inputClass} rows={5} value={criteria} maxLength={50000} onChange={(e) => setCriteria(e.target.value)} />
        </label>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            className={buttonSecondaryClass}
            onClick={() =>
              send(`/api/requirements/${r.id}`, 'PATCH', {
                title,
                description,
                requirement_type: type,
                priority,
                clarifications: answers,
                acceptance_criteria: criteria.split('\n').filter((v) => v.trim()),
              })
            }
          >
            <Save className="size-3.5" aria-hidden="true" />
            Save edits as Draft
          </button>

          <button
            type="button"
            className={buttonSoftAccentClass}
            disabled={dirty}
            onClick={() => send('/api/analyze-requirement', 'POST', analyzePayload, true)}
          >
            <Sparkles className="size-3.5" aria-hidden="true" />
            Analyze saved version / Retry AI
          </button>

          {['Draft', 'Pending', 'Needs Revision'].includes(r.review_status) && (
            <button
              type="button"
              className={buttonPrimaryClass}
              disabled={dirty}
              onClick={() => send(`/api/requirements/${r.id}/submit`, 'POST', {})}
            >
              <Send className="size-3.5" aria-hidden="true" />
              Submit saved requirement for SQA review
            </button>
          )}
        </div>

        <p className="text-[11px] text-muted">
          {dirty ? 'Unsaved edits: save your draft before submitting or attaching analysis. ' : ''}
          Editing an approved requirement requires another review.
        </p>

        {suggestion && (
          <aside className="space-y-4 rounded-xl border border-accent/30 bg-surface p-4" aria-label="Review unconfirmed AI suggestions">
            <AnalysisDraft analysis={suggestion} edits={analysisEdits} onChange={setAnalysisEdits} disabled={busy} />
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Unconfirmed linked scenarios</h3>
              {suggestion.test_scenarios.map((s, i) => (
                <details key={i} className="rounded-lg border border-line bg-surface-alt/40 p-3 text-xs">
                  <summary className="cursor-pointer font-semibold text-ink">
                    {s.title} ({s.criterion_codes.join(', ')})
                  </summary>
                  <p className="mt-2 text-muted">Preconditions: {s.preconditions.join('; ')}</p>
                  <ol className="mt-1 list-decimal pl-4 space-y-0.5 text-ink">
                    {s.test_steps.map((v, j) => <li key={j}>{v}</li>)}
                  </ol>
                  <p className="mt-1 text-ink"><strong>Expected:</strong> {s.expected_result}</p>
                </details>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={buttonPrimaryClass}
                disabled={dirty}
                onClick={() => send(`/api/requirements/${r.id}/analysis`, 'PATCH', { analysis: suggestion, analysis_edits: analysisEdits, title, description })}
              >
                Accept and save analysis with linked scenarios
              </button>
              <button type="button" className={buttonSecondaryClass} onClick={() => setSuggestion(null)}>
                Dismiss suggestions
              </button>
            </div>
          </aside>
        )}
      </fieldset>

      {busy && <p className="text-xs text-muted" role="status">Working… Please wait before retrying.</p>}
      <GeminiErrorBanner
        error={error}
        code={errorCode}
        busy={busy}
        onRetry={errorCode ? () => send('/api/analyze-requirement', 'POST', analyzePayload, true) : undefined}
      />
    </section>
  );
}
