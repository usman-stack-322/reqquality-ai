import React, { useRef, useState } from 'react';
import { apiFetch } from '../api.js';
import AnalysisDraft from './AnalysisDraft';

export default function WorkflowEditor({ requirement: r, user, onUpdate }) {
  const [title, setTitle] = useState(r.title);
  const [description, setDescription] = useState(r.description);
  const [type, setType] = useState(r.requirement_type);
  const [priority, setPriority] = useState(r.user_priority || r.priority);
  const [criteria, setCriteria] = useState(r.acceptance_criteria.map(c => c.description).join('\n'));
  const [answers, setAnswers] = useState(r.analysis_summary?.clarifications || '');
  const [suggestion, setSuggestion] = useState(r.analysis_draft || null);
  const [analysisEdits, setAnalysisEdits] = useState({});
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState('');
  const dirty = title !== r.title || description !== r.description || type !== r.requirement_type
    || priority !== (r.user_priority || r.priority)
    || criteria !== r.acceptance_criteria.map(c => c.description).join('\n')
    || answers !== (r.analysis_summary?.clarifications || '');
  async function send(url, method, data, analysis = false) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      const response = await apiFetch(url, { method, headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ ...data, revision:r.revision }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to save. Retry after reloading the latest revision.');
      if (analysis) { setSuggestion(result); setAnalysisEdits({}); } else onUpdate(result.requirement);
    } catch (e) { setError(e.message); }
    finally { lock.current = false; setBusy(false); }
  }
  const canEdit = user?.role === 'Analyst' && user.permissions?.includes('create_requirements');
  if (!canEdit) return null;
  return <section className="detail-section workflow-editor" aria-busy={busy}>
    <fieldset disabled={busy}><legend>Prepare requirement for review</legend>
      {canEdit && <>
        <p>Project context: {r.project?.context || 'No context supplied; missing values require clarification.'}</p>
        {r.analysis_outdated && <p role="status">Saved analysis is outdated for the current context or configuration. It remains historical evidence; analyze explicitly to update it.</p>}
        <p>Reviewer feedback: {r.reviewer_notes || 'No feedback yet.'}</p>
        <label>Title<input value={title} maxLength={200} onChange={e => {setTitle(e.target.value); setSuggestion(null);}} /></label>
        <label>Description<textarea rows={5} value={description} maxLength={20000} onChange={e => {setDescription(e.target.value); setSuggestion(null);}} /></label>
        <label>Type<select value={type} onChange={e => {setType(e.target.value); setSuggestion(null);}}>{['Functional','Non-Functional','Business'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Priority<select value={priority} onChange={e => {setPriority(e.target.value); setSuggestion(null);}}>{['Low','Medium','High'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Clarification answers<textarea value={answers} maxLength={20000} onChange={e => setAnswers(e.target.value)} /></label>
        <label>Acceptance criteria, one per line<textarea rows={6} value={criteria} maxLength={50000} onChange={e => setCriteria(e.target.value)} /></label>
        <button type="button" disabled={dirty} onClick={() => send('/api/analyze-requirement', 'POST', {title, description, requirement_type:type, priority, clarifications:answers, requirement_id:r.id, requirement_revision:r.revision}, true)}>Analyze saved version / Retry AI</button>
        {suggestion && <aside aria-label="Review unconfirmed AI suggestions">
          <AnalysisDraft analysis={suggestion} edits={analysisEdits} onChange={setAnalysisEdits} disabled={busy} />
          <h3>Unconfirmed linked scenarios</h3>{suggestion.test_scenarios.map((s,i) => <details key={i}><summary>{s.title} ({s.criterion_codes.join(', ')})</summary><p>Preconditions: {s.preconditions.join('; ')}</p><ol>{s.test_steps.map((v,j) => <li key={j}>{v}</li>)}</ol><p>Expected: {s.expected_result}</p></details>)}
          <button type="button" disabled={dirty} onClick={() => send(`/api/requirements/${r.id}/analysis`, 'PATCH', {analysis:suggestion,analysis_edits:analysisEdits,title,description})}>Accept and save analysis with linked scenarios</button><button type="button" onClick={() => setSuggestion(null)}>Dismiss suggestions</button></aside>}
        <button type="button" onClick={() => send(`/api/requirements/${r.id}`, 'PATCH', {title, description, requirement_type:type, priority, clarifications:answers, acceptance_criteria:criteria.split('\n').filter(v => v.trim())})}>Save edits as Draft</button>
        {['Draft','Pending','Needs Revision'].includes(r.review_status) && <button type="button" disabled={dirty} onClick={() => send(`/api/requirements/${r.id}/submit`, 'POST', {})}>Submit saved requirement for SQE review</button>}
        <p>{dirty ? 'Unsaved edits: save your draft before submitting or attaching analysis. ' : ''}Editing an approved requirement requires another review.</p>
      </>}
    </fieldset>
    {busy && <p role="status">Working… Please wait before retrying.</p>}
    {error && <p role="alert" className="error">{error}</p>}
  </section>;
}
