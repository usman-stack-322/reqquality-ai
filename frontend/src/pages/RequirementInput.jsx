import { apiFetch as fetch } from '../api.js';
import React, { useEffect, useState } from 'react';
import SourceBadges from '../components/SourceBadges';

function LabeledItems({ items, defaultSource = 'rule_based' }) {
  if (!items.length) return <p className="analysis-clear">No issues detected by the current rules.</p>;
  return (
    <ul>
      {items.map((entry, index) => {
        const item = typeof entry === 'string'
          ? { text: entry, source: defaultSource, needs_confirmation: defaultSource === 'ai_assumption' }
          : entry;
        return (
          <li key={`${item.source}-${index}-${item.text}`}>
            <span>{item.text}</span>
            <SourceBadges source={item.source} needsConfirmation={item.needs_confirmation} />
            {item.introduced_values?.length > 0 && (
              <span className="introduced-value-list">Introduced values: {item.introduced_values.join(', ')}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function RequirementInput({ csrfToken }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState('Functional');
  const [priority, setPriority] = useState('Medium');
  const [requirements, setRequirements] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [analysisError, setAnalysisError] = useState('');

  useEffect(() => {
    async function loadRequirements() {
      try {
        const response = await fetch('/api/requirements', { credentials: 'include' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Unable to load requirements.');
        setRequirements(data.requirements);
      } catch (error) {
        setErrorMessage(error.message || 'Unable to reach the requirements API.');
      } finally {
        setIsLoading(false);
      }
    }

    loadRequirements();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();

    setIsSaving(true);
    setSuccessMessage('');
    setErrorMessage('');
    try {
      const response = await fetch('/api/requirements', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({
          title,
          description,
          requirement_type: type,
          priority,
          analysis,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save requirement.');

      setRequirements((savedRequirements) => [data.requirement, ...savedRequirements]);
      setSuccessMessage('Requirement saved successfully.');
      setTitle('');
      setDescription('');
      setType('Functional');
      setPriority('Medium');
      setAnalysis(null);
      setAnalysisError('');
    } catch (error) {
      setErrorMessage(error.message || 'Unable to reach the requirements API.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAnalyze() {
    if (!title.trim() || !description.trim()) {
      setAnalysisError('Enter a requirement title and description before analysis.');
      setAnalysis(null);
      return;
    }
    setIsAnalyzing(true);
    setAnalysis(null);
    setAnalysisError('');

    try {
      const response = await fetch('/api/analyze-requirement', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({
          title,
          description,
          requirement_type: type,
          priority,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to analyze requirement.');
      setAnalysis(data);
    } catch (error) {
      setAnalysisError(error.message || 'Unable to reach the analysis API.');
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <div className="requirement-page">
      <section className="card requirement-form-card">
        <div className="requirement-heading">
          <p className="eyebrow">REQUIREMENTS</p>
          <h1>Add Requirement</h1>
          <p>Capture a clear, testable need for your product.</p>
        </div>

        <form className="requirement-form" onSubmit={handleSubmit} aria-busy={isSaving || isAnalyzing}>
          <fieldset className="form-section basic-requirement-section">
            <legend>Basic Requirement Information</legend>
          <div className="requirement-field">
            <label htmlFor="requirement-title">Requirement Title</label>
            <input
              id="requirement-title"
              type="text"
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                setAnalysis(null);
                setAnalysisError('');
              }}
              placeholder="e.g. Export reports as PDF"
              required
              disabled={isSaving || isAnalyzing}
            />
          </div>

          <div className="requirement-field">
            <label htmlFor="requirement-description">Requirement Description</label>
            <textarea
              id="requirement-description"
              rows={5}
              value={description}
              onChange={(event) => {
                setDescription(event.target.value);
                setAnalysis(null);
                setAnalysisError('');
              }}
              placeholder="Describe what the system should do and any important conditions."
              required
              disabled={isSaving || isAnalyzing}
            />
          </div>
          </fieldset>

          <fieldset className="requirement-options form-section">
            <legend>Requirement Type and Priority</legend>
            <div className="requirement-field">
              <label htmlFor="requirement-type">Requirement Type</label>
              <select
                id="requirement-type"
                value={type}
                onChange={(event) => {
                  setType(event.target.value);
                  setAnalysis(null);
                  setAnalysisError('');
                }}
                disabled={isSaving || isAnalyzing}
              >
                <option>Functional</option>
                <option>Non-Functional</option>
                <option>Business</option>
              </select>
            </div>
            <div className="requirement-field">
              <label htmlFor="requirement-priority">Priority</label>
              <select
                id="requirement-priority"
                value={priority}
                onChange={(event) => {
                  setPriority(event.target.value);
                  setAnalysis(null);
                  setAnalysisError('');
                }}
                disabled={isSaving || isAnalyzing}
              >
                <option>High</option>
                <option>Medium</option>
                <option>Low</option>
              </select>
            </div>
          </fieldset>

          <section className="requirement-action-section" aria-labelledby="requirement-actions-title">
            <h2 className="form-actions-heading" id="requirement-actions-title">Actions</h2>
            <div className="requirement-actions">
            <button className="requirement-save-button" type="submit" disabled={isSaving || isAnalyzing}>
              {isSaving ? 'Saving...' : 'Save Requirement'}
            </button>
            <button
              className="requirement-analyze-button"
              type="button"
              onClick={handleAnalyze}
              disabled={isAnalyzing || isSaving}
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze with AI'}
            </button>
            </div>
            {isAnalyzing && <p className="form-loading-status" role="status"><span className="loading-dot" aria-hidden="true" />Analyzing against the rules and available AI model...</p>}
            {isSaving && <p className="form-loading-status" role="status"><span className="loading-dot" aria-hidden="true" />Saving requirement and traceability data...</p>}
            {successMessage && <p className="notice notice-success" role="status">{successMessage}</p>}
            {errorMessage && <p className="notice notice-error" role="alert">{errorMessage}</p>}
            {analysisError && <p className="notice notice-error" role="alert">{analysisError}</p>}
          </section>
        </form>
      </section>

      {analysis && (
        <section className="analysis-results" aria-labelledby="analysis-results-title">
          <div className="analysis-results-heading">
            <p className="eyebrow">
              {analysis.analysis_mode === 'hybrid' ? 'HYBRID REVIEW' : 'RULE-BASED REVIEW'}
            </p>
            <h2 id="analysis-results-title">Requirement analysis</h2>
            <p className="analysis-status">
              {analysis.analysis_mode === 'hybrid' ? 'Rules + Gemini' : 'Rule-based only'}
              {analysis.llm_status && ` | Gemini: ${analysis.llm_status.replaceAll('_', ' ')}`}
            </p>
          </div>
          <article className="card original-requirement-card">
            <div className="analysis-item-heading">
              <h3>Original stakeholder requirement</h3>
              <SourceBadges source="original" />
            </div>
            <strong>{analysis.labeled_analysis?.original_requirement?.title || title}</strong>
            <p>{analysis.labeled_analysis?.original_requirement?.description || description}</p>
          </article>
          <article className={`card risk-summary risk-${analysis.risk_level?.toLowerCase() || 'low'}`}>
            <div className="risk-summary-heading">
              <h3>Quality risk</h3>
              <span className="risk-score">{analysis.risk_score}/100</span>
            </div>
            <div className="risk-summary-details">
              <p><strong>Risk level</strong><span>{analysis.risk_level}</span></p>
              <p><strong>Suggested priority</strong><span>{analysis.suggested_priority}</span></p>
            </div>
            <h4>Risk reasons</h4>
            <ul>{(analysis.risk_reasons || []).map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </article>
          <section className="test-scenarios" aria-labelledby="test-scenarios-title">
            <div className="test-scenarios-heading">
              <h3 id="test-scenarios-title">Generated Test Scenarios</h3>
              <span>{analysis.test_scenario_source === 'gemini' ? 'Gemini generated' : 'Deterministic fallback'}</span>
            </div>
            <div className="scenario-groups">
              {[
                ['Positive', 'Positive scenarios'],
                ['Negative', 'Negative scenarios'],
                ['Boundary', 'Boundary scenarios'],
                ['Edge-case', 'Edge-case scenarios'],
              ].map(([category, heading]) => {
                const scenarios = (analysis.test_scenarios || []).filter(
                  (scenario) => scenario.category === category,
                );
                return (
                  <article className="card scenario-group" key={category}>
                    <h4>{heading}</h4>
                    {scenarios.map((scenario) => (
                      <section className="scenario-item" key={scenario.id}>
                        <div className="scenario-title-row">
                          <h5>{scenario.title}</h5>
                          <span>{scenario.id}</span>
                        </div>
                        <SourceBadges source={scenario.source || 'rule_based'} needsConfirmation={scenario.needs_confirmation} />
                        {scenario.assumption_reasons?.length > 0 && (
                          <p className="confirmation-note">Depends on unconfirmed AI assumptions: {scenario.assumption_reasons.join(' ')}</p>
                        )}
                        {scenario.introduced_values?.length > 0 && (
                          <p className="introduced-value-list">AI-introduced values: {scenario.introduced_values.join(', ')}</p>
                        )}
                        <p><strong>Preconditions</strong></p>
                        <ul>{scenario.preconditions.map((item) => <li key={item}>{item}</li>)}</ul>
                        <p><strong>Test steps</strong></p>
                        <ol>{scenario.test_steps.map((step, index) => <li key={`${scenario.id}-${index}`}>{step}</li>)}</ol>
                        <p><strong>Expected result</strong></p>
                        <p>{scenario.expected_result}</p>
                        <p className="scenario-linked-requirement">Linked requirement: {scenario.linked_requirement}</p>
                      </section>
                    ))}
                    {scenarios.length === 0 && <p className="analysis-clear">No scenarios available.</p>}
                  </article>
                );
              })}
            </div>
          </section>
          <div className="analysis-grid">
            {[
              ['Ambiguity', 'ambiguity_issues', analysis.ambiguity_issues || [], 'rule_based'],
              ['Missing information', 'missing_information', analysis.missing_information || [], 'rule_based'],
              ['Testability', 'testability_issues', analysis.testability_issues || [], 'rule_based'],
              ['Assumptions', 'assumptions', analysis.assumptions || [], 'ai_assumption'],
              ['Possible edge cases', 'edge_cases', analysis.edge_cases || [], 'rule_based'],
              ['Acceptance criteria', 'acceptance_criteria', analysis.acceptance_criteria || [], 'rule_based'],
            ].map(([heading, field, fallbackItems, fallbackSource]) => {
              const items = analysis.labeled_analysis?.[field] || fallbackItems;
              return (
              <article className="card analysis-card" key={heading}>
                <h3>{heading}</h3>
                <LabeledItems items={items} defaultSource={fallbackSource} />
              </article>
              );
            })}
            <article className="card analysis-card improved-requirement-card">
              <div className="analysis-item-heading">
                <h3>Suggested improved requirement</h3>
                <SourceBadges
                  source={analysis.labeled_analysis?.improved_requirement?.source || (analysis.analysis_mode === 'hybrid' ? 'ai_suggestion' : 'rule_based')}
                  needsConfirmation={analysis.labeled_analysis?.improved_requirement?.needs_confirmation}
                />
              </div>
              <p>{analysis.labeled_analysis?.improved_requirement?.text || analysis.improved_requirement}</p>
              {analysis.labeled_analysis?.improved_requirement?.introduced_values?.length > 0 && (
                <div className="confirmation-note">
                  <strong>AI-introduced values:</strong>
                  <ul className="introduced-value-chips">
                    {analysis.labeled_analysis.improved_requirement.introduced_values.map((value) => (
                      <li key={value}>{value}</li>
                    ))}
                  </ul>
                  <p>These values are suggestions and require stakeholder/SQA confirmation before they are treated as requirements.</p>
                </div>
              )}
            </article>
          </div>
        </section>
      )}

      <section className="saved-requirements" aria-labelledby="saved-requirements-title">
        <div className="saved-requirements-heading">
          <h2 id="saved-requirements-title">Saved requirements</h2>
          <span>{requirements.length}</span>
        </div>
        {isLoading ? (
          <p className="requirements-empty">Loading requirements...</p>
        ) : requirements.length === 0 ? (
          <p className="requirements-empty">Your saved requirements will appear here.</p>
        ) : (
          <div className="requirements-list">
            {requirements.map((requirement) => (
              <article className="card saved-requirement-card" key={requirement.id}>
                <div className="saved-requirement-title-row">
                  <h3>{requirement.title}</h3>
                  <span className={`priority-label priority-${(requirement.user_priority || requirement.priority).toLowerCase()}`}>
                    {requirement.user_priority || requirement.priority}
                  </span>
                </div>
                <p className="saved-requirement-description">{requirement.description}</p>
                <span className="requirement-type-label">{requirement.requirement_type || requirement.type}</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
