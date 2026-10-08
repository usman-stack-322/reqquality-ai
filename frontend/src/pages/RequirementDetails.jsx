import { apiFetch as fetch } from '../api.js';
import PdfExportButton from '../components/PdfExportButton';
import React, { useEffect, useState } from 'react';
import SourceBadges from '../components/SourceBadges';

const REVIEW_STATUSES = ['Pending', 'In Review', 'Approved', 'Needs Revision'];
const SCENARIO_CATEGORIES = ['Positive', 'Negative', 'Boundary', 'Edge-case'];
const ANALYSIS_GROUPS = [
  ['Ambiguity', 'ambiguity_issues', 'rule_based'],
  ['Missing information', 'missing_information', 'rule_based'],
  ['Testability', 'testability_issues', 'rule_based'],
  ['Assumptions', 'assumptions', 'ai_assumption'],
  ['Possible edge cases', 'edge_cases', 'rule_based'],
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
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    async function loadRequirement() {
      setIsLoading(true);
      setError('');
      try {
        const response = await fetch(`/api/requirements/${requirementId}`, { credentials: 'include' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Unable to load requirement details.');
        setRequirement(data.requirement);
        setReviewStatus(data.requirement.review_status);
        setReviewerNotes(data.requirement.reviewer_notes || '');
      } catch (loadError) {
        setError(loadError.message || 'Unable to reach the requirements API.');
      } finally {
        setIsLoading(false);
      }
    }
    loadRequirement();
  }, [requirementId, revision]);

  useEffect(() => {
    if (openReview && requirement && !isLoading) document.getElementById('sqa-review-title')?.scrollIntoView({ block: 'start' });
  }, [openReview, requirement, isLoading]);

  async function handleSaveReview(event) {
    event.preventDefault();
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      const response = await fetch(`/api/requirements/${requirementId}/review`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ review_status: reviewStatus, reviewer_notes: reviewerNotes }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save the SQA review.');
      setRequirement(data.requirement);
      setReviewStatus(data.requirement.review_status);
      setReviewerNotes(data.requirement.reviewer_notes || '');
      setMessage('SQA review saved.');
    } catch (saveError) {
      setError(saveError.message || 'Unable to reach the requirements API.');
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <p className="requirements-empty">Loading requirement...</p>;
  if (error && !requirement) return <p className="error" role="alert">{error} <a href={managerView ? '#admin/requirements' : '#dashboard'}>Return to requirements</a></p>;
  if (!requirement) return null;
  const canReview = user?.permissions?.includes('review_requirements');
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
        <div className="detail-title-row">
          <div>
            <h1>{requirement.title}</h1>
            <p>{requirement.description}</p>
            <SourceBadges source="original" confirmed={requirement.review_status === 'Approved'} />
          </div>
          <span className={`review-status review-${requirement.review_status.toLowerCase().replaceAll(' ', '-')}`}>
            {requirement.review_status}
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

      {hasSavedAnalysis && (
        <section className="detail-section saved-analysis-section" aria-labelledby="saved-analysis-title">
          <div className="detail-section-heading">
            <h2 id="saved-analysis-title">Saved Hybrid Analysis</h2>
            <span>{savedAnalysis.analysis_mode === 'hybrid' ? 'Rules + Gemini' : 'Rule-based'}</span>
          </div>
          <div className="analysis-grid">
            {ANALYSIS_GROUPS.map(([heading, field, fallbackSource]) => (
              <article className="card analysis-card" key={field}>
                <h3>{heading}</h3>
                <AnalysisItems
                  items={savedAnalysis.labeled_analysis?.[field] || savedAnalysis[field] || []}
                  fallbackSource={fallbackSource}
                  confirmed={requirement.review_status === 'Approved'}
                />
              </article>
            ))}
            {savedAnalysis.improved_requirement && (
              <article className="card analysis-card improved-requirement-card">
                <div className="analysis-item-heading">
                  <h3>Suggested improved requirement</h3>
                  <SourceBadges
                    source={savedAnalysis.labeled_analysis?.improved_requirement?.source || 'rule_based'}
                    needsConfirmation={savedAnalysis.labeled_analysis?.improved_requirement?.needs_confirmation}
                    confirmed={requirement.review_status === 'Approved'}
                  />
                </div>
                <p>{savedAnalysis.labeled_analysis?.improved_requirement?.text || savedAnalysis.improved_requirement}</p>
                {savedAnalysis.labeled_analysis?.improved_requirement?.introduced_values?.length > 0 && (
                  <p className="introduced-value-list">AI-introduced values: {savedAnalysis.labeled_analysis.improved_requirement.introduced_values.join(', ')}</p>
                )}
              </article>
            )}
          </div>
        </section>
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
                <div><p>{assumption.description}</p><SourceBadges source={assumption.source} needsConfirmation={assumption.needs_confirmation} confirmed={requirement.review_status === 'Approved'} /></div>
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
                  <SourceBadges source={criterion.source} needsConfirmation={criterion.needs_confirmation} confirmed={requirement.review_status === 'Approved'} />
                  {criterion.introduced_values.length > 0 && <span className="introduced-value-list">AI-introduced values: {criterion.introduced_values.join(', ')}</span>}
                </div>
              </li>
            ))}
          </ol>
        ) : <p className="requirements-empty">No acceptance criteria were saved with this requirement.</p>}
      </section>

      <section className="detail-section" aria-labelledby="linked-scenarios-title">
        <div className="detail-section-heading">
          <h2 id="linked-scenarios-title">Linked Test Scenarios</h2>
          <span>{requirement.test_scenarios.length}</span>
        </div>
        <div className="scenario-groups">
          {SCENARIO_CATEGORIES.map((category) => {
            const scenarios = requirement.test_scenarios.filter((item) => item.category === category);
            return (
              <article className="card scenario-group" key={category}>
                <h3>{category} scenarios</h3>
                {scenarios.map((scenario) => (
                  <div className="scenario-item" key={scenario.id}>
                    <div className="scenario-title-row"><h4>{scenario.title}</h4><span>{scenario.scenario_code}</span></div>
                    <SourceBadges source={scenario.source} needsConfirmation={scenario.needs_confirmation} confirmed={requirement.review_status === 'Approved'} />
                    {scenario.assumption_reasons.length > 0 && <p className="confirmation-note">Depends on AI assumptions: {scenario.assumption_reasons.join(' ')}</p>}
                    {scenario.introduced_values.length > 0 && <p className="introduced-value-list">AI-introduced values: {scenario.introduced_values.join(', ')}</p>}
                    <p><strong>Preconditions</strong></p>
                    <ul>{scenario.preconditions.map((item, index) => <li key={`${scenario.id}-pre-${index}`}>{item}</li>)}</ul>
                    <p><strong>Test steps</strong></p>
                    <ol>{scenario.test_steps.map((step, index) => <li key={`${scenario.id}-step-${index}`}>{step}</li>)}</ol>
                    <p><strong>Expected result</strong></p>
                    <p>{scenario.expected_result}</p>
                  </div>
                ))}
                {!scenarios.length && <p className="analysis-clear">No linked scenarios in this category.</p>}
              </article>
            );
          })}
        </div>
      </section>

      <section className="detail-section sqa-review" aria-labelledby="sqa-review-title">
        <div className="detail-section-heading">
          <h2 id="sqa-review-title">SQA Review</h2>
          <span>{requirement.review_status}</span>
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
              <textarea id="reviewer-notes" rows={5} value={reviewerNotes} onChange={(event) => setReviewerNotes(event.target.value)} disabled={isSaving} placeholder="Record review findings or requested changes." />
            </div>
            <button className="requirement-save-button" type="submit" disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save Review'}
            </button>
            {message && <p className="success" role="status">{message}</p>}
            {error && <p className="error" role="alert">{error}</p>}
          </form>
        ) : (
          <div className="review-read-only">
            <p><strong>Review Status</strong><span className={`review-status review-${requirement.review_status.toLowerCase().replaceAll(' ', '-')}`}>{requirement.review_status}</span></p>
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
