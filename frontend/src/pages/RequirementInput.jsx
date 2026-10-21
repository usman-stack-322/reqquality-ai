import { apiFetch as fetch } from '../api.js';
import React, { useRef, useState } from 'react';
import AnalysisDraft from '../components/AnalysisDraft';
import ProjectContext from '../components/ProjectContext';

export default function RequirementInput({ csrfToken }) {
  const busy = useRef(false);
  const submission = useRef(null);
  const [accepted, setAccepted] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState('Functional');
  const [priority, setPriority] = useState('Medium');
  const [isSaving, setIsSaving] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [analysisEdits, setAnalysisEdits] = useState({});
  const [analysisError, setAnalysisError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy.current) return;
    if (analysis && !accepted) { setErrorMessage('Review and accept the analysis before saving it.'); return; }
    busy.current = true;
    const body = JSON.stringify({title, description, requirement_type:type, priority, analysis, analysis_edits:analysisEdits});
    if (submission.current?.body !== body) submission.current = {body, key:globalThis.crypto.randomUUID()};
    setIsSaving(true);
    setSuccessMessage('');
    setErrorMessage('');
    try {
      const response = await fetch('/api/requirements', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken, 'Idempotency-Key': submission.current.key },
        body,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save requirement.');

      window.location.hash = `requirement/${data.requirement.id}`;
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
      busy.current = false;
      setIsSaving(false);
    }
  }

  async function handleAnalyze() {
    if (busy.current) return;
    if (!title.trim() || !description.trim()) {
      setAnalysisError('Enter a requirement title and description before analysis.');
      setAnalysis(null);
      return;
    }
    busy.current = true;
    setAccepted(false);
    setAnalysisEdits({});
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
      busy.current = false;
      setIsAnalyzing(false);
    }
  }

  return (
    <div className="requirement-page"><a className="back-link" href="#dashboard">? Dashboard</a><ProjectContext />
      <section className="card requirement-form-card">
        <div className="requirement-heading">
          <p className="eyebrow">REQUIREMENTS</p>
          <h1>Add Requirement</h1>
          <p>Save a draft, then review AI findings and submit it to your SQE.</p>
        </div>

        <form className="requirement-form" onSubmit={handleSubmit} aria-busy={isSaving || isAnalyzing}>
          <fieldset className="form-section basic-requirement-section">
            <legend>Basic Requirement Information</legend>
          <div className="requirement-field">
            <label htmlFor="requirement-title">Requirement Title</label>
            <input
              id="requirement-title"
              maxLength={200}
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
              maxLength={20000}
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
              {isAnalyzing ? 'Analyzing...' : analysisError ? 'Retry AI analysis' : 'Analyze with AI'}
            </button>
            </div>
            {isAnalyzing && <p className="form-loading-status" role="status"><span className="loading-dot" aria-hidden="true" />Analyzing with Gemini. Your text stays here if you need to retry...</p>}
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
              AI REVIEW
            </p>
            <h2 id="analysis-results-title">Requirement analysis</h2>
            <p>Suggestions require human review. Risk indicates requirement-quality concerns, not proven defects. Generated scenarios have not been executed.</p>
            <p className="analysis-status">
              Gemini semantic analysis
              {analysis.llm_status && ` | Gemini: ${analysis.llm_status.replaceAll('_', ' ')}`}
            </p>
          </div>
          <AnalysisDraft analysis={analysis} edits={analysisEdits} onChange={value => {setAnalysisEdits(value); setAccepted(false);}} disabled={isSaving || isAnalyzing} />
          <label><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} /> I have reviewed these unconfirmed suggestions and accept saving them for review.</label>
          <p>Save this draft to continue refining and submit it for SQE review.</p>

        </section>
      )}

    </div>
  );
}
