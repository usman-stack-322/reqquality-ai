import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, CheckCircle2, ClipboardCheck, FlaskConical, GitBranch, Sparkles, UserCheck } from 'lucide-react';
import { apiFetch as fetch } from '../api.js';
import IntegratedReview from '../components/IntegratedReview';
import PdfExportButton from '../components/PdfExportButton';
import SourceBadges from '../components/SourceBadges';
import WorkflowEditor from '../components/WorkflowEditor';
import TestCases from '../components/TestCases';
import LoadingSkeleton from '../components/LoadingSkeleton';
import AIReviewAssistant from '../components/AIReviewAssistant';
import TraceabilityStepper from '../components/TraceabilityStepper';
import { StatusBadge, buttonPrimaryClass, buttonSecondaryClass, buttonSoftAccentClass, inputClass } from '../components/ui';

const REVIEW_STATUSES = ['In Review', 'Approved', 'Needs Revision'];
const ANALYSIS_GROUPS = [
  ['Ambiguity', 'ambiguity_issues', 'ai_suggestion'],
  ['Conflicts', 'conflict_issues', 'ai_suggestion'],
  ['Missing information', 'missing_information', 'ai_suggestion'],
  ['Clarification questions', 'clarification_questions', 'ai_suggestion'],
  ['Testability', 'testability_issues', 'ai_suggestion'],
  ['Assumptions', 'assumptions', 'ai_assumption'],
  ['Possible edge cases', 'edge_cases', 'ai_suggestion'],
  ['Risk explanation', 'risk_reasons', 'ai_suggestion'],
  ['Priority explanation', 'priority_reasons', 'ai_suggestion'],
];

function AnalysisItems({ items, fallbackSource, confirmed }) {
  if (!items?.length) return <p className="text-xs text-muted">No findings recorded.</p>;
  return (
    <ul className="space-y-2 text-xs">
      {items.map((entry, index) => {
        const item =
          typeof entry === 'string'
            ? { text: entry, source: fallbackSource, needs_confirmation: fallbackSource === 'ai_assumption' }
            : entry;
        return (
          <li key={`${item.source}-${index}-${item.text}`} className="space-y-1">
            <p className="text-ink">{item.text}</p>
            <SourceBadges source={item.source} needsConfirmation={item.needs_confirmation} confirmed={confirmed} />
            {item.introduced_values?.length > 0 && (
              <span className="block text-[11px] text-warning">
                AI-introduced values: {item.introduced_values.join(', ')}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function RequirementDetails({
  requirementId,
  user,
  csrfToken,
  managerView = false,
  onAssign,
  openReview = false,
  revision = 0,
}) {
  const [requirement, setRequirement] = useState(null);
  const [traceability, setTraceability] = useState(null);
  const [reviewStatus, setReviewStatus] = useState('Pending');
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const reviewLock = useRef(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [retry, setRetry] = useState(0);
  const [rightTab, setRightTab] = useState('ai');
  const [aiCaseIds, setAiCaseIds] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadRequirement() {
      setIsLoading(true);
      setError('');
      try {
        const [reqResponse, traceResponse] = await Promise.all([
          fetch(`/api/requirements/${requirementId}`, { signal: controller.signal }),
          fetch(`/api/requirements/${requirementId}/traceability`, { signal: controller.signal }).catch(() => null),
        ]);
        const data = await reqResponse.json();
        if (!reqResponse.ok) throw new Error(data.error || 'Unable to load requirement details.');
        const traceData = traceResponse?.ok ? await traceResponse.json().catch(() => null) : null;
        if (controller.signal.aborted) return;
        setRequirement(data.requirement);
        setTraceability(traceData);
        setReviewStatus(data.requirement.sqa_review_status === 'Pending' ? 'In Review' : data.requirement.review_status);
        setReviewerNotes(data.requirement.reviewer_notes || '');
      } catch (loadError) {
        if (controller.signal.aborted) return;
        setError(loadError.message || 'Unable to reach the requirements API.');
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }
    loadRequirement();
    return () => controller.abort();
  }, [requirementId, revision, retry]);

  useEffect(() => {
    if (openReview && requirement && !isLoading) {
      document.getElementById('sqa-review-title')?.scrollIntoView({ block: 'start' });
    }
  }, [openReview, requirement, isLoading]);

  async function saveReview(targetStatus = reviewStatus) {
    if (reviewLock.current) return;
    reviewLock.current = true;
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      const response = await fetch(`/api/requirements/${requirementId}/review`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ review_status: targetStatus, reviewer_notes: reviewerNotes, revision: requirement.revision }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save the SQA review.');
      setRequirement(data.requirement);
      setReviewStatus(data.requirement.sqa_review_status === 'Pending' ? 'In Review' : data.requirement.review_status);
      setReviewerNotes(data.requirement.reviewer_notes || '');
      setMessage('SQA review saved.');
    } catch (saveError) {
      setError(saveError.message || 'Unable to reach the requirements API.');
    } finally {
      reviewLock.current = false;
      setIsSaving(false);
    }
  }

  function jumpToSection(sectionId) {
    if (sectionId === 'cases-section') setRightTab('cases');
    setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  }

  if (isLoading) return <LoadingSkeleton label="Loading requirement" />;
  if (error && !requirement) {
    return (
      <div className="rounded-xl border border-danger/35 bg-danger-tint p-4 text-xs text-danger space-y-3" role="alert">
        <p>{error}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={buttonSecondaryClass} onClick={() => setRetry((v) => v + 1)}>Retry requirement</button>
          <a className={`${buttonSecondaryClass} no-underline`} href={managerView ? '#admin/requirements' : '#dashboard'}>Return to requirements</a>
        </div>
      </div>
    );
  }
  if (!requirement) return null;

  const canReview =
    user?.role === 'SQA Engineer' &&
    user.id !== requirement.created_by_user_id &&
    user?.permissions?.includes('review_requirements') &&
    (['Pending', 'Ready for Review', 'In Review'].includes(requirement.review_status) ||
      (requirement.review_status === 'Approved' && !requirement.review_valid));
  const canAssistant =
    (user?.role === 'Analyst' && user.permissions?.includes('create_requirements')) ||
    (user?.role === 'SQA Engineer' && user.permissions?.includes('review_requirements'));

  const reviewedAt = requirement.reviewed_at ? new Date(requirement.reviewed_at).toLocaleString() : 'Not reviewed yet';
  const savedAnalysis = requirement.analysis_summary || {};
  const hasSavedAnalysis = ANALYSIS_GROUPS.some(([, field]) => savedAnalysis[field]?.length) || Boolean(savedAnalysis.improved_requirement);
  const improvedText = savedAnalysis.labeled_analysis?.improved_requirement?.text || savedAnalysis.improved_requirement;
  const activeCasesCount = requirement.test_scenarios?.length || 0;
  const bugCount = traceability?.bugs?.length || 0;
  const hasExecutions = Boolean(traceability?.executions?.some((e) => e.requirement_revision === requirement.content_revision));

  return (
    <div className="requirement-detail-page space-y-6">
      <div className="detail-actions flex flex-wrap items-center justify-between gap-3">
        <a
          className="back-link inline-flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-ink no-underline"
          href={managerView ? '#admin/requirements' : '#dashboard'}
        >
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          All requirements
        </a>
        <div className="flex flex-wrap items-center gap-2.5">
          {managerView && (
            <button type="button" className={buttonSecondaryClass} onClick={() => onAssign(requirement)}>
              <UserCheck className="size-3.5" aria-hidden="true" />
              Assign / Reassign Reviewer
            </button>
          )}
          <PdfExportButton url={`/api/requirements/${requirement.id}/report.pdf`} filename={`requirement-${requirement.id}.pdf`} />
        </div>
      </div>

      <TraceabilityStepper
        reviewStatus={requirement.review_status}
        sqaReviewStatus={requirement.sqa_review_status}
        hasAnalysis={hasSavedAnalysis}
        hasExecutions={hasExecutions}
        criteriaCount={requirement.acceptance_criteria?.length || 0}
        caseCount={activeCasesCount}
        bugCount={bugCount}
        onJump={jumpToSection}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12 items-start">
        {/* Left Pane: Immutable Source, Criteria, Metadata, Analyst Workflow & SQA Decision */}
        <div className="xl:col-span-6 space-y-6 min-w-0">
          <section className="requirement-detail-heading rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="font-mono text-xs font-semibold text-accent">REQUIREMENT REQ-{requirement.id} · v{requirement.content_revision}</p>
                <h1 className="text-xl font-bold text-ink">{requirement.title}</h1>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <StatusBadge value={requirement.review_status} />
                <StatusBadge value={requirement.sqa_review_status} />
              </div>
            </div>

            <p className="rounded-lg border border-line bg-surface-alt/50 p-3.5 text-sm leading-relaxed text-ink whitespace-pre-wrap">
              {requirement.description}
            </p>

            <div className="flex flex-wrap items-center gap-2">
              <SourceBadges source="original" confirmed={requirement.review_valid} />
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5 text-xs font-medium text-ink">
                {requirement.requirement_type}
              </span>
              <StatusBadge value={requirement.risk_level || 'Not analyzed'} />
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5 text-xs text-muted">
                User priority: <strong className="text-ink">{requirement.user_priority || requirement.priority}</strong>
              </span>
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5 text-xs text-muted">
                AI priority: <strong className="text-ink">{requirement.suggested_priority || 'Not analyzed'}</strong>
              </span>
            </div>

            <p className="text-xs text-muted" role="status">
              Authoring: <strong className="text-ink">{requirement.review_status}</strong>.{' '}
              {user?.role === 'Analyst'
                ? requirement.review_status === 'Ready for Review'
                  ? 'Submitted to the SQE review queue. Your saved draft is ready for review.'
                  : 'Save your draft, review AI suggestions, then submit for SQE review.'
                : 'Inspect criteria and test cases, record Manual execution where permitted, then save your review decision below.'}
            </p>
          </section>

          <section id="criteria-section" className="detail-section rounded-xl border border-line bg-surface p-5 shadow-xs space-y-3" aria-labelledby="criteria-title">
            <div className="flex items-center justify-between gap-2">
              <h2 id="criteria-title" className="text-base font-semibold text-ink">Acceptance Criteria</h2>
              <span className="rounded-md border border-line bg-surface-alt px-2 py-0.5 text-xs font-semibold text-ink tabular-nums">
                {requirement.acceptance_criteria.length}
              </span>
            </div>
            {requirement.acceptance_criteria.length ? (
              <ol className="space-y-2.5">
                {requirement.acceptance_criteria.map((criterion) => (
                  <li key={criterion.criterion_code} className="rounded-lg border border-line bg-surface-alt/40 p-3 space-y-1.5">
                    <div className="flex items-start gap-2.5">
                      <span className="rounded bg-accent-tint px-1.5 py-0.5 font-mono text-[11px] font-semibold text-accent shrink-0">
                        {criterion.criterion_code}
                      </span>
                      <p className="text-xs text-ink">{criterion.description}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 pl-1">
                      <SourceBadges source={criterion.source} needsConfirmation={criterion.needs_confirmation} confirmed={requirement.review_valid} />
                      {criterion.introduced_values.length > 0 && (
                        <span className="text-[11px] text-warning">AI-introduced values: {criterion.introduced_values.join(', ')}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-xs text-muted">No acceptance criteria were saved with this requirement.</p>
            )}
          </section>

          {(requirement.assumptions.length > 0 || savedAnalysis.risk_reasons?.length > 0 || savedAnalysis.priority_reasons?.length > 0) && (
            <section className="detail-section rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4" aria-labelledby="quality-risk-title">
              <div className="flex items-center justify-between gap-2">
                <h2 id="quality-risk-title" className="text-base font-semibold text-ink">Risk, Priority &amp; Assumptions</h2>
                <span className="text-xs font-medium text-muted">
                  {requirement.risk_score === null ? 'Unscored' : `${requirement.risk_score}/100`}
                </span>
              </div>
              {requirement.assumptions.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">AI Assumptions</h3>
                  <ul className="space-y-2">
                    {requirement.assumptions.map((assumption) => (
                      <li key={assumption.assumption_code} className="rounded-lg border border-line bg-surface-alt/40 p-3 text-xs space-y-1">
                        <p className="text-ink">{assumption.description}</p>
                        <SourceBadges source={assumption.source} needsConfirmation={assumption.needs_confirmation} confirmed={requirement.review_valid} />
                        {assumption.introduced_values.length > 0 && (
                          <span className="block text-[11px] text-warning">Values: {assumption.introduced_values.join(', ')}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(savedAnalysis.risk_reasons?.length > 0 || savedAnalysis.priority_reasons?.length > 0) && (
                <ul className="list-disc pl-4 space-y-1 text-xs text-muted">
                  {[...(savedAnalysis.risk_reasons || []), ...(savedAnalysis.priority_reasons || [])].map((text, i) => (
                    <li key={i}>{text}</li>
                  ))}
                </ul>
              )}
              <p className="text-[11px] text-muted">
                Requirement-quality risk: {requirement.risk_level || 'Not analyzed'}. Suggested priority: {requirement.suggested_priority || 'Not analyzed'}. These indicate review attention, not proven software defects.
              </p>
            </section>
          )}

          <WorkflowEditor key={`${requirement.id}-${requirement.revision}`} requirement={requirement} user={user} onUpdate={setRequirement} />

          <section className="detail-section sqa-review rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4" aria-labelledby="sqa-review-title">
            <div className="flex items-center justify-between gap-2">
              <h2 id="sqa-review-title" className="text-base font-semibold text-ink">SQA Review</h2>
              <StatusBadge value={requirement.sqa_review_status} />
            </div>

            {canReview ? (
              <form
                className="review-form space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  saveReview(reviewStatus);
                }}
              >
                <label className="block space-y-1 text-xs font-medium text-ink">
                  <span>Review Status</span>
                  <select className={inputClass} id="review-status" value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)} disabled={isSaving}>
                    {REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}
                  </select>
                </label>
                <label className="block space-y-1 text-xs font-medium text-ink">
                  <span>Reviewer Notes</span>
                  <textarea
                    className={inputClass}
                    id="reviewer-notes"
                    rows={4}
                    maxLength={20000}
                    value={reviewerNotes}
                    onChange={(event) => setReviewerNotes(event.target.value)}
                    disabled={isSaving}
                    placeholder="Record review findings or requested changes."
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  <button className={buttonPrimaryClass} type="submit" disabled={isSaving}>
                    <CheckCircle2 className="size-3.5" aria-hidden="true" />
                    {isSaving ? 'Saving...' : 'Save Review'}
                  </button>
                  {requirement.review_status === 'In Review' && (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-success/35 bg-success-tint px-3.5 py-2 text-xs font-semibold text-success hover:brightness-105 disabled:opacity-50"
                      disabled={isSaving}
                      onClick={() => saveReview('Approved')}
                    >
                      Approve
                    </button>
                  )}
                </div>
                {message && <p className="rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">{message}</p>}
                {error && <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">{error}</p>}
              </form>
            ) : (
              <dl className="grid grid-cols-1 gap-2.5 text-xs sm:grid-cols-2">
                <div className="rounded-lg border border-line bg-surface-alt/40 p-2.5">
                  <dt className="text-muted">Reviewed content version</dt>
                  <dd className="mt-0.5 font-semibold text-ink">{requirement.reviewed_content_revision || 'Not version-verified'}</dd>
                </div>
                <div className="rounded-lg border border-line bg-surface-alt/40 p-2.5">
                  <dt className="text-muted">Assigned reviewer</dt>
                  <dd className="mt-0.5 font-semibold text-ink">{requirement.assigned_reviewer || 'Unassigned'}</dd>
                </div>
                <div className="rounded-lg border border-line bg-surface-alt/40 p-2.5">
                  <dt className="text-muted">Reviewed by</dt>
                  <dd className="mt-0.5 font-semibold text-ink">{requirement.reviewed_by_name || 'Not recorded'}</dd>
                </div>
                <div className="rounded-lg border border-line bg-surface-alt/40 p-2.5">
                  <dt className="text-muted">Reviewed at</dt>
                  <dd className="mt-0.5 font-semibold text-ink">{reviewedAt}</dd>
                </div>
                <div className="sm:col-span-2 rounded-lg border border-line bg-surface-alt/40 p-2.5">
                  <dt className="text-muted">Reviewer notes</dt>
                  <dd className="mt-0.5 text-ink">{requirement.reviewer_notes || 'No reviewer notes.'}</dd>
                </div>
                <p className="sm:col-span-2 text-[11px] text-muted">SQA Engineers record review decisions.</p>
              </dl>
            )}
          </section>
        </div>

        {/* Right Pane: Gemini Analysis Diffs, Conversational AI Assistant, Test Cases & Traceability */}
        <div className="xl:col-span-6 space-y-4 min-w-0">
          <div className="flex flex-wrap items-center gap-1 rounded-xl border border-line bg-surface p-1 shadow-xs" role="tablist" aria-label="Requirement workspace panels">
            {[
              ['ai', 'Gemini & AI Review', Sparkles],
              ['cases', `Test Cases (${activeCasesCount})`, FlaskConical],
              ['traceability', 'Traceability & Versions', GitBranch],
            ].map(([key, label, TabIcon]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={rightTab === key}
                onClick={() => setRightTab(key)}
                className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
                  rightTab === key ? 'bg-accent-tint text-accent' : 'text-muted hover:text-ink'
                }`}
              >
                <TabIcon className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="truncate">{label}</span>
              </button>
            ))}
          </div>

          {rightTab === 'ai' && (
            <div className="space-y-4">
              {savedAnalysis.stale && (
                <p className="rounded-xl border border-warning/30 bg-warning-tint px-4 py-2.5 text-xs text-warning" role="status">
                  The requirement was edited after this analysis. These findings describe an earlier revision.
                </p>
              )}

              {hasSavedAnalysis ? (
                <section className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <h2 id="saved-analysis-title" className="text-base font-semibold text-ink">Saved Gemini Analysis</h2>
                      <p className="text-xs text-muted">Side-by-side comparison and structured quality findings</p>
                    </div>
                    <ClipboardCheck className="size-4 text-accent" aria-hidden="true" />
                  </div>

                  {improvedText && (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <section className="rounded-lg border border-line bg-surface-alt/60 p-3 space-y-1.5">
                        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">Original text</h3>
                        <p className="text-xs text-ink whitespace-pre-wrap">{requirement.description}</p>
                      </section>
                      <section className="rounded-lg border border-accent/30 bg-accent-tint/50 p-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-accent">Proposed improvement</h3>
                          <SourceBadges
                            source={savedAnalysis.labeled_analysis?.improved_requirement?.source || (savedAnalysis.analysis_mode === 'ai_only' ? 'ai_suggestion' : 'rule_based')}
                            needsConfirmation={savedAnalysis.labeled_analysis?.improved_requirement?.needs_confirmation}
                            confirmed={requirement.review_valid}
                          />
                        </div>
                        <p className="text-xs text-ink whitespace-pre-wrap">{improvedText}</p>
                        {savedAnalysis.labeled_analysis?.improved_requirement?.introduced_values?.length > 0 && (
                          <p className="text-[11px] text-warning">
                            AI-introduced values: {savedAnalysis.labeled_analysis.improved_requirement.introduced_values.join(', ')}
                          </p>
                        )}
                      </section>
                    </div>
                  )}

                  {savedAnalysis.type_explanation && (
                    <article className="rounded-lg border border-line bg-surface-alt/40 p-3 text-xs space-y-1">
                      <h3 className="font-semibold text-ink">Suggested type: {savedAnalysis.suggested_requirement_type}</h3>
                      <p className="text-muted">{savedAnalysis.type_explanation}</p>
                    </article>
                  )}

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {ANALYSIS_GROUPS.filter(([, field]) => field !== 'assumptions' && field !== 'risk_reasons' && field !== 'priority_reasons').map(([heading, field, fallbackSource]) => (
                      <article className="rounded-lg border border-line bg-surface-alt/30 p-3 space-y-2" key={field}>
                        <h3 className="text-xs font-semibold text-ink">{heading}</h3>
                        <AnalysisItems
                          items={savedAnalysis.labeled_analysis?.[field] || savedAnalysis[field] || []}
                          fallbackSource={savedAnalysis.analysis_mode === 'ai_only' ? fallbackSource : 'rule_based'}
                          confirmed={requirement.review_valid}
                        />
                      </article>
                    ))}
                  </div>
                </section>
              ) : (
                <section className="rounded-xl border border-dashed border-line bg-surface p-5 text-center space-y-1.5">
                  <p className="text-sm font-semibold text-ink">No saved AI analysis yet</p>
                  <p className="text-xs text-muted">Analysts can run Gemini analysis on the saved draft, or use the AI Review Assistant below.</p>
                </section>
              )}

              {canAssistant && (
                <div className="space-y-2">
                  {aiCaseIds.length > 0 && (
                    <div className="flex items-center justify-between rounded-lg border border-accent/25 bg-accent-tint px-3 py-2 text-xs">
                      <span className="font-medium text-accent">Discussing {aiCaseIds.map((id) => `TC-${id}`).join(', ')}</span>
                      <button type="button" className={buttonSoftAccentClass} onClick={() => setAiCaseIds([])}>
                        Switch to requirement coverage
                      </button>
                    </div>
                  )}
                  <AIReviewAssistant
                    key={`${requirement.id}-${aiCaseIds.join(',')}`}
                    requirement={requirement}
                    caseIds={aiCaseIds}
                    user={user}
                    inline
                    onUpdate={setRequirement}
                  />
                </div>
              )}
            </div>
          )}

          {rightTab === 'cases' && (
            <div id="cases-section">
              <TestCases
                key={requirement.id}
                requirement={requirement}
                user={user}
                onUpdate={setRequirement}
                onRequestRevision={(ids) => {
                  setAiCaseIds(ids);
                  setRightTab('ai');
                }}
              />
            </div>
          )}

          {rightTab === 'traceability' && (
            <IntegratedReview key={requirement.id} requirement={requirement} user={user} initialData={traceability} />
          )}
        </div>
      </div>
    </div>
  );
}
