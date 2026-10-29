import IntegratedReview from '../components/IntegratedReview';
import { apiFetch as fetch } from '../api.js';
import PdfExportButton from '../components/PdfExportButton';
import React, { useEffect, useRef, useState } from 'react';
import SourceBadges from '../components/SourceBadges';
import WorkflowEditor from '../components/WorkflowEditor';
import TestCases from '../components/TestCases';
import LoadingSkeleton from '../components/LoadingSkeleton';

const REVIEW_STATUSES = ['In Review', 'Approved', 'Needs Revision'];
const SCENARIO_CATEGORIES = ['Positive', 'Negative', 'Boundary', 'Edge-case'];
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
  if (!items?.length) return <p className="analysis-clear">No findings recorded.</p>;
  return (
    <ul>
      {items.map((entry, index) => {
        const item = typeof entry === 'string'
          ? { text: entry, source: fallbackSource, needs_confirmation: fallbackSource === 'ai_assumption' }
          : entry;
        return (
          <li key={`${item.source}-${index}-${item.text}`}>
            <span>{item.text}</span>
            <SourceBadges source={item.source} needsConfirmation={item.needs_confirmation} confirmed={confirmed} />
            {item.introduced_values?.length > 0 && (
              <span className="introduced-value-list">AI-introduced values: {item.introduced_values.join(', ')}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function RequirementDetails({ requirementId, user, csrfToken, managerView = false, onAssign, openReview = false, revision = 0 }) {
  const [requirement, setRequirement] = useState(null);
  const [reviewStatus, setReviewStatus] = useState('Pending');
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const reviewLock = useRef(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [retry,setRetry]=useState(0);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function loadRequirement() {
      setIsLoading(true);
      setError('');
      try {
        const response = await fetch(`/api/requirements/${requirementId}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Unable to load requirement details.');
        if (controller.signal.aborted) return;
        setRequirement(data.requirement);
        setReviewStatus(data.requirement.sqa_review_status==='Pending' ? 'In Review' : data.requirement.review_status);
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
  }, [requirementId, revision,retry]);

  useEffect(() => {
    if (openReview && requirement && !isLoading) document.getElementById('sqa-review-title')?.scrollIntoView({ block: 'start' });
  }, [openReview, requirement, isLoading]);

  async function handleSaveReview(event) {
    event.preventDefault();
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
        body: JSON.stringify({ review_status: reviewStatus, reviewer_notes: reviewerNotes, revision: requirement.revision }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save the SQA review.');
      setRequirement(data.requirement);
      setReviewStatus(data.requirement.sqa_review_status==='Pending' ? 'In Review' : data.requirement.review_status);
      setReviewerNotes(data.requirement.reviewer_notes || '');
      setMessage('SQA review saved.');
    } catch (saveError) {
      setError(saveError.message || 'Unable to reach the requirements API.');
    } finally {
      reviewLock.current = false;
      setIsSaving(false);
    }
  }

  if (isLoading) return <LoadingSkeleton label="Loading requirement" />;
  if (error && !requirement) return <p className="error" role="alert">{error} <button onClick={()=>setRetry(v=>v+1)}>Retry requirement</button><a href={managerView ? '#admin/requirements' : '#dashboard'}>Return to requirements</a></p>;
  if (!requirement) return null;
  const canReview = user?.role === 'SQA Engineer' && user.id !== requirement.created_by_user_id && user?.permissions?.includes('review_requirements') && (['Pending', 'Ready for Review', 'In Review'].includes(requirement.review_status) || (requirement.review_status==='Approved'&&!requirement.review_valid));
  const reviewedAt = requirement.reviewed_at
    ? new Date(requirement.reviewed_at).toLocaleString()
    : 'Not reviewed yet';
  const savedAnalysis = requirement.analysis_summary || {};
  const hasSavedAnalysis = ANALYSIS_GROUPS.some(([, field]) => savedAnalysis[field]?.length)
    || Boolean(savedAnalysis.improved_requirement);

  return (
    <div className="requirement-detail-page">
      <div className="detail-actions">
        <a className="back-link" href={managerView ? '#admin/requirements' : '#dashboard'}>&larr; All requirements</a>
        {managerView && <button onClick={() => onAssign(requirement)}>Assign / Reassign Reviewer</button>}
        <PdfExportButton url={`/api/requirements/${requirement.id}/report.pdf`} filename={`requirement-${requirement.id}.pdf`} />
      </div>
      <section className="requirement-detail-heading">
        <p className="eyebrow">REQUIREMENT {requirement.id}</p>
        <p role="status">Authoring: {requirement.review_status}. {user?.role === 'Analyst'
          ? requirement.review_status === 'Ready for Review' ? 'Submitted to the SQE review queue. Your saved draft is ready for review.' : 'Save your draft, review AI suggestions, then submit for SQE review.'
          : 'Inspect criteria and test cases, record Manual execution where permitted, then save your review decision below.'}</p>
        <div className="detail-title-row">
          <div>
            <h1>{requirement.title}</h1>
            <p>{requirement.description}</p>
            <SourceBadges source="original" confirmed={requirement.review_valid} />
          </div>
          <span className={`review-status review-${requirement.review_status.toLowerCase().replaceAll(' ', '-')}`}>
            {requirement.sqa_review_status}
          </span>
        </div>
        <div className="requirement-metadata">
          <span>{requirement.requirement_type}</span>
          <span className={`risk-level risk-${(requirement.risk_level || 'unscored').toLowerCase()}`}>
            Risk: {requirement.risk_level || 'Not analyzed'}{requirement.risk_score !== null && ` · ${requirement.risk_score}/100`}
          </span>
          <span className="priority-label priority-medium">
            Suggested priority: {requirement.suggested_priority || 'Not analyzed'}
          </span>
        </div>
      </section>

      <WorkflowEditor key={`${requirement.id}-${requirement.revision}`} requirement={requirement} user={user} onUpdate={setRequirement} />
      {savedAnalysis.stale && <p role="status">The requirement was edited after this analysis. These findings describe an earlier revision.</p>}
      {hasSavedAnalysis && (
        <details className="detail-section saved-analysis-section"><summary id="saved-analysis-title">Saved AI findings: suggestions requiring review</summary>

          <div className="analysis-grid">
            {savedAnalysis.improved_requirement && (
              <article className="card analysis-card improved-requirement-card">
                <div className="analysis-item-heading">
                  <h3>Suggested improved requirement</h3>
                  <SourceBadges
                    source={savedAnalysis.labeled_analysis?.improved_requirement?.source || (savedAnalysis.analysis_mode === 'ai_only' ? 'ai_suggestion' : 'rule_based')}
                    needsConfirmation={savedAnalysis.labeled_analysis?.improved_requirement?.needs_confirmation}
                    confirmed={requirement.review_valid}
                  />
                </div>
                <p>{savedAnalysis.labeled_analysis?.improved_requirement?.text || savedAnalysis.improved_requirement}</p>
                {savedAnalysis.labeled_analysis?.improved_requirement?.introduced_values?.length > 0 && (
                  <p className="introduced-value-list">AI-introduced values: {savedAnalysis.labeled_analysis.improved_requirement.introduced_values.join(', ')}</p>
                )}
              </article>
            )}
            {savedAnalysis.type_explanation && <article className="card analysis-card"><h3>Suggested type: {savedAnalysis.suggested_requirement_type}</h3><p>{savedAnalysis.type_explanation}</p></article>}
            {ANALYSIS_GROUPS.filter(([, field]) => field !== 'assumptions' && field !== 'risk_reasons' && field !== 'priority_reasons').map(([heading, field, fallbackSource]) => (
              <article className="card analysis-card" key={field}>
                <h3>{heading}</h3>
                <AnalysisItems
                  items={savedAnalysis.labeled_analysis?.[field] || savedAnalysis[field] || []}
                  fallbackSource={savedAnalysis.analysis_mode === 'ai_only' ? fallbackSource : 'rule_based'}
                  confirmed={requirement.review_valid}
                />
              </article>
            ))}
          </div>
        </details>
      )}

      {requirement.assumptions.length > 0 && (
        <section className="detail-section" aria-labelledby="assumptions-title">
          <div className="detail-section-heading">
            <h2 id="assumptions-title">AI Assumptions</h2>
            <span>{requirement.assumptions.length}</span>
          </div>
          <ul className="labeled-detail-list">
            {requirement.assumptions.map((assumption) => (
              <li key={assumption.assumption_code}>
                <div><p>{assumption.description}</p><SourceBadges source={assumption.source} needsConfirmation={assumption.needs_confirmation} confirmed={requirement.review_valid} /></div>
                {assumption.introduced_values.length > 0 && <span className="introduced-value-list">Values: {assumption.introduced_values.join(', ')}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="detail-section" aria-labelledby="criteria-title">
        <div className="detail-section-heading">
          <h2 id="criteria-title">Acceptance Criteria</h2>
          <span>{requirement.acceptance_criteria.length}</span>
        </div>
        {requirement.acceptance_criteria.length ? (
          <ol className="criteria-list">
            {requirement.acceptance_criteria.map((criterion) => (
              <li key={criterion.criterion_code}>
                <span>{criterion.criterion_code}</span>
                <div className="labeled-detail-copy">
                  <p>{criterion.description}</p>
                  <SourceBadges source={criterion.source} needsConfirmation={criterion.needs_confirmation} confirmed={requirement.review_valid} />
                  {criterion.introduced_values.length > 0 && <span className="introduced-value-list">AI-introduced values: {criterion.introduced_values.join(', ')}</span>}
                </div>
              </li>
            ))}
          </ol>
        ) : <p className="requirements-empty">No acceptance criteria were saved with this requirement.</p>}
      </section>

      <section className="detail-section" aria-labelledby="quality-risk-title">
        <div className="detail-section-heading"><h2 id="quality-risk-title">Risk / Priority</h2><span>{requirement.risk_score === null ? 'Unscored' : `${requirement.risk_score}/100`}</span></div>
        <ul>{[...(savedAnalysis.risk_reasons || []), ...(savedAnalysis.priority_reasons || [])].map((text,i) => <li key={i}>{text}</li>)}</ul>
        <p>Requirement-quality risk: {requirement.risk_level || 'Not analyzed'}. Suggested priority: {requirement.suggested_priority || 'Not analyzed'}. These indicate review attention, not proven software defects.</p>
      </section>

      <details className="detail-section" onToggle={event => setShowHistory(event.currentTarget.open)}><summary>Version history and traceability</summary>{showHistory && <IntegratedReview key={requirement.id} requirement={requirement} user={user} />}</details>
      <TestCases key={requirement.id} requirement={requirement} user={user} onUpdate={setRequirement} />
      <section className="detail-section sqa-review" aria-labelledby="sqa-review-title">
        <div className="detail-section-heading">
          <h2 id="sqa-review-title">SQA Review</h2>
          <span>{requirement.sqa_review_status}</span>
        </div>
        {canReview ? (
          <form className="review-form" onSubmit={handleSaveReview}>
            <div className="requirement-field">
              <label htmlFor="review-status">Review Status</label>
              <select id="review-status" value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)} disabled={isSaving}>
                {REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}
              </select>
            </div>
            <div className="requirement-field">
              <label htmlFor="reviewer-notes">Reviewer Notes</label>
              <textarea id="reviewer-notes" rows={5} maxLength={20000} value={reviewerNotes} onChange={(event) => setReviewerNotes(event.target.value)} disabled={isSaving} placeholder="Record review findings or requested changes." />
            </div>
            <button className="requirement-save-button" type="submit" disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save Review'}
            </button>
            {message && <p className="success" role="status">{message}</p>}
            {error && <p className="error" role="alert">{error}</p>}
          </form>
        ) : (
          <div className="review-read-only">
            <p><strong>Reviewed content version</strong><span>{requirement.reviewed_content_revision || 'Not version-verified'}</span></p><p><strong>Review Status</strong><span className={`review-status review-${requirement.review_status.toLowerCase().replaceAll(' ', '-')}`}>{requirement.sqa_review_status}</span></p>
            <p><strong>Reviewer Notes</strong><span>{requirement.reviewer_notes || 'No reviewer notes.'}</span></p>
            <p><strong>Assigned reviewer</strong><span>{requirement.assigned_reviewer || 'Unassigned'}</span></p>
            <p><strong>Reviewed by</strong><span>{requirement.reviewed_by_name || 'Not recorded'}</span></p>
            <p><strong>Reviewed at</strong><span>{reviewedAt}</span></p>
            <p className="field-hint">SQA Engineers record review decisions.</p>
          </div>
        )}
      </section>
    </div>
  );
}
