import { apiFetch as fetch } from '../api.js';
import React, { useRef, useState } from 'react';
import { ArrowLeft, Save, Sparkles } from 'lucide-react';
import AnalysisDraft from '../components/AnalysisDraft';
import ProjectContext from '../components/ProjectContext';
import TraceabilityStepper from '../components/TraceabilityStepper';
import { GeminiErrorBanner, PageHeader, StatusBadge, buttonPrimaryClass, buttonSoftAccentClass, inputClass } from '../components/ui';

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
  const [analysisErrorCode, setAnalysisErrorCode] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    if (busy.current) return;
    if (analysis && !accepted) {
      setErrorMessage('Review and accept the analysis before saving it.');
      return;
    }
    busy.current = true;
    const body = JSON.stringify({ title, description, requirement_type: type, priority, analysis, analysis_edits: analysisEdits });
    if (submission.current?.body !== body) submission.current = { body, key: globalThis.crypto.randomUUID() };
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
      setAnalysisErrorCode('');
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
      setAnalysisErrorCode('');
      setAnalysis(null);
      return;
    }
    busy.current = true;
    setAccepted(false);
    setAnalysisEdits({});
    setIsAnalyzing(true);
    setAnalysis(null);
    setAnalysisError('');
    setAnalysisErrorCode('');

    try {
      const response = await fetch('/api/analyze-requirement', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ title, description, requirement_type: type, priority }),
      });
      const data = await response.json();
      if (!response.ok) {
        const err = new Error(data.error || 'Unable to analyze requirement.');
        err.code = data.code || '';
        throw err;
      }
      setAnalysis(data);
    } catch (error) {
      setAnalysisError(error.message || 'Unable to reach the analysis API.');
      setAnalysisErrorCode(error.code || '');
    } finally {
      busy.current = false;
      setIsAnalyzing(false);
    }
  }

  const effectiveAnalysis = analysis ? { ...analysis, ...analysisEdits } : null;

  return (
    <div className="requirement-page space-y-6">
      <div className="flex items-center justify-between gap-3">
        <a className="back-link inline-flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-ink no-underline" href="#dashboard">
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Back to Requirements
        </a>
      </div>

      <PageHeader
        eyebrow="Requirements · New Draft"
        title="Add Requirement"
        description="Save a draft, analyze quality with Gemini, review proposed refinements, and submit to SQA."
      />

      <TraceabilityStepper
        reviewStatus="Draft"
        hasAnalysis={Boolean(analysis)}
        criteriaCount={effectiveAnalysis?.acceptance_criteria?.length || 0}
        caseCount={analysis?.test_scenarios?.length || 0}
        bugCount={0}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12 items-start">
        <div className="xl:col-span-5 space-y-6">
          <section className="card requirement-form-card rounded-xl border border-line bg-surface p-5 shadow-xs space-y-5">
            <form className="requirement-form space-y-4" onSubmit={handleSubmit} aria-busy={isSaving || isAnalyzing}>
              <fieldset className="form-section basic-requirement-section space-y-4">
                <legend className="text-xs font-semibold uppercase tracking-wider text-accent">Basic Requirement Information</legend>
                <div className="requirement-field space-y-1">
                  <label htmlFor="requirement-title" className="block text-xs font-semibold text-ink">Requirement Title</label>
                  <input
                    id="requirement-title"
                    className={inputClass}
                    maxLength={200}
                    type="text"
                    value={title}
                    onChange={(event) => {
                      setTitle(event.target.value);
                      setAnalysis(null);
                      setAnalysisError('');
                      setAnalysisErrorCode('');
                    }}
                    placeholder="e.g. Export reports as PDF"
                    required
                    disabled={isSaving || isAnalyzing}
                  />
                </div>

                <div className="requirement-field space-y-1">
                  <label htmlFor="requirement-description" className="block text-xs font-semibold text-ink">Requirement Description</label>
                  <textarea
                    id="requirement-description"
                    className={inputClass}
                    maxLength={20000}
                    rows={6}
                    value={description}
                    onChange={(event) => {
                      setDescription(event.target.value);
                      setAnalysis(null);
                      setAnalysisError('');
                      setAnalysisErrorCode('');
                    }}
                    placeholder="Describe what the system should do and any important conditions."
                    required
                    disabled={isSaving || isAnalyzing}
                  />
                </div>
              </fieldset>

              <fieldset className="requirement-options form-section grid grid-cols-1 gap-3 sm:grid-cols-2">
                <legend className="text-xs font-semibold uppercase tracking-wider text-accent col-span-full mb-1">Type and Priority</legend>
                <div className="requirement-field space-y-1">
                  <label htmlFor="requirement-type" className="block text-xs font-semibold text-ink">Requirement Type</label>
                  <select
                    id="requirement-type"
                    className={inputClass}
                    value={type}
                    onChange={(event) => {
                      setType(event.target.value);
                      setAnalysis(null);
                      setAnalysisError('');
                      setAnalysisErrorCode('');
                    }}
                    disabled={isSaving || isAnalyzing}
                  >
                    <option>Functional</option>
                    <option>Non-Functional</option>
                    <option>Business</option>
                  </select>
                </div>
                <div className="requirement-field space-y-1">
                  <label htmlFor="requirement-priority" className="block text-xs font-semibold text-ink">Priority</label>
                  <select
                    id="requirement-priority"
                    className={inputClass}
                    value={priority}
                    onChange={(event) => {
                      setPriority(event.target.value);
                      setAnalysis(null);
                      setAnalysisError('');
                      setAnalysisErrorCode('');
                    }}
                    disabled={isSaving || isAnalyzing}
                  >
                    <option>High</option>
                    <option>Medium</option>
                    <option>Low</option>
                  </select>
                </div>
              </fieldset>

              <section className="requirement-action-section space-y-3 border-t border-line pt-4" aria-labelledby="requirement-actions-title">
                <h2 className="sr-only" id="requirement-actions-title">Actions</h2>
                <div className="requirement-actions flex flex-wrap gap-2.5">
                  <button className={`${buttonPrimaryClass} requirement-save-button`} type="submit" disabled={isSaving || isAnalyzing}>
                    <Save className="size-3.5" aria-hidden="true" />
                    {isSaving ? 'Saving...' : 'Save Requirement'}
                  </button>
                  <button
                    className={`${buttonSoftAccentClass} requirement-analyze-button`}
                    type="button"
                    onClick={handleAnalyze}
                    disabled={isAnalyzing || isSaving}
                  >
                    <Sparkles className="size-3.5" aria-hidden="true" />
                    {isAnalyzing ? 'Analyzing...' : analysisError ? 'Retry AI analysis' : 'Analyze with AI'}
                  </button>
                </div>
                {isAnalyzing && (
                  <p className="text-xs text-muted" role="status">
                    Analyzing with Gemini. Your text stays here if you need to retry…
                  </p>
                )}
                {isSaving && (
                  <p className="text-xs text-muted" role="status">
                    Saving requirement and traceability data…
                  </p>
                )}
                {successMessage && (
                  <p className="rounded-lg border border-success/30 bg-success-tint px-3 py-2 text-xs text-success" role="status">
                    {successMessage}
                  </p>
                )}
                {errorMessage && (
                  <p className="rounded-lg border border-danger/30 bg-danger-tint px-3 py-2 text-xs text-danger" role="alert">
                    {errorMessage}
                  </p>
                )}
              </section>
            </form>
          </section>

          <ProjectContext />
        </div>

        <div className="xl:col-span-7 space-y-4">
          <GeminiErrorBanner
            error={analysisError}
            code={analysisErrorCode}
            busy={isAnalyzing || isSaving}
            onRetry={handleAnalyze}
          />

          {analysis ? (
            <section className="analysis-results rounded-xl border border-line bg-surface p-5 shadow-xs space-y-5" aria-labelledby="analysis-results-title">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">AI Review</p>
                  <h2 id="analysis-results-title" className="text-lg font-bold text-ink">Requirement analysis</h2>
                  <p className="text-xs text-muted">
                    Suggestions require human review. Risk indicates requirement-quality concerns, not proven defects.
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <StatusBadge value={effectiveAnalysis.risk_level} />
                  <StatusBadge value={effectiveAnalysis.suggested_priority} />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <section className="rounded-xl border border-line bg-surface-alt/60 p-3.5 space-y-1.5">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Original requirement</h3>
                  <p className="text-xs font-semibold text-ink">{title}</p>
                  <p className="text-xs text-muted whitespace-pre-wrap">{description}</p>
                </section>
                <section className="rounded-xl border border-accent/30 bg-accent-tint/50 p-3.5 space-y-1.5">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-accent">Proposed improvement</h3>
                  <p className="text-xs text-ink whitespace-pre-wrap">{effectiveAnalysis.improved_requirement}</p>
                </section>
              </div>

              <AnalysisDraft
                analysis={analysis}
                edits={analysisEdits}
                onChange={(value) => {
                  setAnalysisEdits(value);
                  setAccepted(false);
                }}
                disabled={isSaving || isAnalyzing}
              />

              <label className="flex items-start gap-2.5 rounded-lg border border-line bg-surface-alt/50 p-3 text-xs font-medium text-ink cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                />
                <span>I have reviewed these unconfirmed suggestions and accept saving them for review.</span>
              </label>
            </section>
          ) : (
            <section className="rounded-xl border border-dashed border-line bg-surface p-8 text-center space-y-2">
              <div className="mx-auto inline-flex size-10 items-center justify-center rounded-xl bg-accent-tint text-accent">
                <Sparkles className="size-5" aria-hidden="true" />
              </div>
              <h2 className="text-sm font-semibold text-ink">Gemini Quality Analysis Workspace</h2>
              <p className="mx-auto max-w-md text-xs text-muted">
                Enter your requirement title and description on the left, then click <strong>Analyze with AI</strong> to generate ambiguities, acceptance criteria, risk rationale, and linked scenarios.
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
