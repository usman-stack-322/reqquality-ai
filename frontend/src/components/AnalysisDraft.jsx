import React, { useEffect, useState } from 'react';

function DraftLines({ label, items, onChange }) {
  const text=items.join('\n');
  const [raw,setRaw]=useState(text);
  useEffect(()=>{
    setRaw(current=>current.split('\n').filter(v=>v.trim()).join('\n')===text?current:text);
  },[text]);
  return <label>{label}, one per line<textarea rows={3} maxLength={50000} value={raw} onChange={e=>{
    setRaw(e.target.value);onChange(e.target.value.split('\n').filter(v=>v.trim()));
  }} /></label>;
}

export default function AnalysisDraft({ analysis, edits, onChange, disabled = false }) {
  const value = { ...analysis, ...edits };
  const set = (key, entry) => onChange({ ...edits, [key]: entry });
  return <fieldset disabled={disabled}><legend>Editable proposal — original requirement stays unchanged</legend>
    <p>AI suggestions require stakeholder review. Missing values remain unresolved; saving does not approve this proposal.</p>
    <label>Proposed refined requirement<textarea rows={5} maxLength={20000} value={value.improved_requirement} onChange={e => set('improved_requirement', e.target.value)} /></label>
    <label>Suggested requirement type<select value={value.suggested_requirement_type} onChange={e => set('suggested_requirement_type', e.target.value)}>{['Functional', 'Non-Functional', 'Business'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Type explanation<textarea maxLength={5000} value={value.type_explanation} onChange={e => set('type_explanation', e.target.value)} /></label>
    {[['Ambiguities', 'ambiguity_issues'], ['Conflicts', 'conflict_issues'], ['Missing information', 'missing_information'], ['Clarification questions', 'clarification_questions'], ['Testability', 'testability_issues'], ['Assumptions', 'assumptions'], ['Acceptance criteria', 'acceptance_criteria'], ['Risk explanations', 'risk_reasons'], ['Priority explanations', 'priority_reasons']].map(([label, key]) => <DraftLines key={key} label={label} items={value[key] || []} onChange={entry=>set(key,entry)} />)}
    <label>Suggested risk<select value={value.risk_level} onChange={e => set('risk_level', e.target.value)}>{['Low', 'Medium', 'High', 'Critical'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Suggested priority<select value={value.suggested_priority} onChange={e => set('suggested_priority', e.target.value)}>{['Low', 'Medium', 'High'].map(v => <option key={v}>{v}</option>)}</select></label>
    <p>Criterion positions define AC-001, AC-002, etc. Existing scenario links must still match the edited criteria.</p>
  </fieldset>;
}
