import React, { useRef, useState } from 'react';
import { apiFetch } from '../api.js';

function ScenarioEditor({ scenario, requirement, send }) {
  const [title, setTitle] = useState(scenario.title);
  const [steps, setSteps] = useState(scenario.test_steps.join('\n'));
  const [expected, setExpected] = useState(scenario.expected_result);
  const [codes, setCodes] = useState(scenario.criterion_codes || []);
  return <details><summary>Revise {scenario.scenario_code}: {scenario.title}</summary>
    <label>Scenario title<input value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
    <label>Test steps, one per line<textarea value={steps} onChange={e => setSteps(e.target.value)} /></label>
    <label>Expected result<textarea value={expected} onChange={e => setExpected(e.target.value)} /></label>
    <fieldset><legend>Linked acceptance criteria</legend>{requirement.acceptance_criteria.map(c => <label key={c.criterion_code}><input type="checkbox" checked={codes.includes(c.criterion_code)} onChange={e => setCodes(e.target.checked ? [...codes,c.criterion_code] : codes.filter(v => v !== c.criterion_code))} />{c.criterion_code}: {c.description}</label>)}</fieldset>
    <button type="button" onClick={() => send(`/api/requirements/${requirement.id}/scenarios/${scenario.id}`, 'PATCH', { ...scenario, title, test_steps: steps.split('\n').filter(Boolean), expected_result: expected, criterion_codes: codes })}>Save scenario revision</button>
  </details>;
}

export default function WorkflowEditor({ requirement: r, user, onUpdate }) {
  const [title, setTitle] = useState(r.title);
  const [description, setDescription] = useState(r.description);
  const [type, setType] = useState(r.requirement_type);
  const [priority, setPriority] = useState(r.user_priority || r.priority);
  const [criteria, setCriteria] = useState(r.acceptance_criteria.map(c => c.description).join('\n'));
  const [answers, setAnswers] = useState(r.analysis_summary?.clarifications || '');
  const [suggestion, setSuggestion] = useState(null);
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
      if (analysis) setSuggestion(result); else onUpdate(result.requirement);
    } catch (e) { setError(e.message); }
    finally { lock.current = false; setBusy(false); }
  }
  const canEdit = user?.role === 'Analyst' && user.permissions?.includes('create_requirements');
  const canReview = user?.role === 'SQA Engineer' && user.id !== r.created_by_user_id && user.permissions?.includes('review_requirements') && ['Pending','Ready for Review','In Review'].includes(r.review_status);
  if (!canEdit && !canReview) return null;
  return <section className="detail-section workflow-editor" aria-busy={busy}>
    <fieldset disabled={busy}><legend>{canEdit ? 'Prepare requirement for review' : 'Revise linked test scenarios'}</legend>
      {canEdit && <>
        <p>Reviewer feedback: {r.reviewer_notes || 'No feedback yet.'}</p>
        <label>Title<input value={title} maxLength={200} onChange={e => {setTitle(e.target.value); setSuggestion(null);}} /></label>
        <label>Description<textarea rows={5} value={description} maxLength={20000} onChange={e => {setDescription(e.target.value); setSuggestion(null);}} /></label>
        <label>Type<select value={type} onChange={e => {setType(e.target.value); setSuggestion(null);}}>{['Functional','Non-Functional','Business'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Priority<select value={priority} onChange={e => {setPriority(e.target.value); setSuggestion(null);}}>{['Low','Medium','High'].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Clarification answers<textarea value={answers} maxLength={20000} onChange={e => setAnswers(e.target.value)} /></label>
        <label>Acceptance criteria, one per line<textarea rows={6} value={criteria} maxLength={50000} onChange={e => setCriteria(e.target.value)} /></label>
        <button type="button" onClick={() => send('/api/analyze-requirement', 'POST', {title, description, requirement_type:type, priority, clarifications:answers}, true)}>Analyze current text</button>
        {suggestion && <aside aria-label="Review unconfirmed AI suggestions"><p>Unconfirmed AI refinement: {suggestion.improved_requirement}</p>
          <p>Suggested type: {suggestion.suggested_requirement_type}. {suggestion.type_explanation}</p>
          <p>Qualitative AI risk: {suggestion.risk_level}. Suggested priority: {suggestion.suggested_priority}. Both require review.</p>
          {[['Ambiguity','ambiguity_issues'],['Conflicts','conflict_issues'],['Clarification questions','missing_information'],['Testability','testability_issues'],['Assumptions','assumptions'],['Acceptance criteria','acceptance_criteria'],['Risk explanation','risk_reasons'],['Priority explanation','priority_reasons']].map(([label,key]) => <div key={key}><h3>{label}</h3><ul>{(suggestion[key] || []).map((v,i) => <li key={i}>{v}</li>)}</ul></div>)}
          <h3>Unconfirmed linked scenarios</h3>{suggestion.test_scenarios.map((s,i) => <details key={i}><summary>{s.title} ({s.criterion_codes.join(', ')})</summary><p>Preconditions: {s.preconditions.join('; ')}</p><ol>{s.test_steps.map((v,j) => <li key={j}>{v}</li>)}</ol><p>Expected: {s.expected_result}</p></details>)}
          <button type="button" disabled={dirty} onClick={() => send(`/api/requirements/${r.id}/analysis`, 'PATCH', {analysis:suggestion,title,description})}>Accept and save analysis with linked scenarios</button><button type="button" onClick={() => { setDescription(suggestion.improved_requirement); setCriteria(suggestion.acceptance_criteria.join('\n')); setSuggestion(null); }}>Accept refinement and criteria into this draft</button><button type="button" onClick={() => setSuggestion(null)}>Dismiss suggestions</button></aside>}
        <button type="button" onClick={() => send(`/api/requirements/${r.id}`, 'PATCH', {title, description, requirement_type:type, priority, clarifications:answers, acceptance_criteria:criteria.split('\n').filter(v => v.trim())})}>Save edits as Draft</button>
        {['Draft','Pending','Needs Revision'].includes(r.review_status) && <button type="button" disabled={dirty} onClick={() => send(`/api/requirements/${r.id}/submit`, 'POST', {})}>Submit saved requirement for SQE review</button>}
        <p>{dirty ? 'Unsaved edits: save your draft before submitting or attaching analysis. ' : ''}Editing an approved requirement requires another review.</p>
      </>}
      {canReview && r.test_scenarios.map(s => <ScenarioEditor key={s.id} scenario={s} requirement={r} send={send} />)}
    </fieldset>
    {busy && <p role="status">Working… Please wait before retrying.</p>}
    {error && <p role="alert" className="error">{error}</p>}
  </section>;
}
