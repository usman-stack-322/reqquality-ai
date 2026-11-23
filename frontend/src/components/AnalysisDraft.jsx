import React, { useEffect, useState } from 'react';
import { inputClass } from '../components/ui';

function DraftLines({ label, items, onChange }) {
  const text = items.join('\n');
  const [raw, setRaw] = useState(text);
  useEffect(() => {
    setRaw((current) =>
      current.split('\n').filter((v) => v.trim()).join('\n') === text ? current : text,
    );
  }, [text]);

  return (
    <label className="block space-y-1 text-xs font-medium text-ink">
      <span>{label}, one per line</span>
      <textarea
        className={inputClass}
        rows={3}
        maxLength={50000}
        value={raw}
        onChange={(e) => {
          setRaw(e.target.value);
          onChange(e.target.value.split('\n').filter((v) => v.trim()));
        }}
      />
    </label>
  );
}

export default function AnalysisDraft({ analysis, edits, onChange, disabled = false }) {
  const value = { ...analysis, ...edits };
  const set = (key, entry) => onChange({ ...edits, [key]: entry });

  return (
    <fieldset disabled={disabled} className="space-y-4 rounded-xl border border-line bg-surface-alt/30 p-4">
      <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-accent">
        Editable proposal — original requirement stays unchanged
      </legend>
      <p className="text-xs text-muted">
        AI suggestions require stakeholder review. Missing values remain unresolved; saving does not approve this proposal.
      </p>

      <label className="block space-y-1 text-xs font-medium text-ink">
        <span>Proposed refined requirement</span>
        <textarea
          className={inputClass}
          rows={4}
          maxLength={20000}
          value={value.improved_requirement}
          onChange={(e) => set('improved_requirement', e.target.value)}
        />
      </label>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Suggested type</span>
          <select
            className={inputClass}
            value={value.suggested_requirement_type}
            onChange={(e) => set('suggested_requirement_type', e.target.value)}
          >
            {['Functional', 'Non-Functional', 'Business'].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Suggested risk</span>
          <select className={inputClass} value={value.risk_level} onChange={(e) => set('risk_level', e.target.value)}>
            {['Low', 'Medium', 'High', 'Critical'].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1 text-xs font-medium text-ink">
          <span>Suggested priority</span>
          <select
            className={inputClass}
            value={value.suggested_priority}
            onChange={(e) => set('suggested_priority', e.target.value)}
          >
            {['Low', 'Medium', 'High'].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="block space-y-1 text-xs font-medium text-ink">
        <span>Type explanation</span>
        <textarea
          className={inputClass}
          rows={2}
          maxLength={5000}
          value={value.type_explanation}
          onChange={(e) => set('type_explanation', e.target.value)}
        />
      </label>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {[
          ['Acceptance criteria', 'acceptance_criteria'],
          ['Ambiguities', 'ambiguity_issues'],
          ['Conflicts', 'conflict_issues'],
          ['Missing information', 'missing_information'],
          ['Clarification questions', 'clarification_questions'],
          ['Testability', 'testability_issues'],
          ['Assumptions', 'assumptions'],
          ['Risk explanations', 'risk_reasons'],
          ['Priority explanations', 'priority_reasons'],
        ].map(([label, key]) => (
          <DraftLines key={key} label={label} items={value[key] || []} onChange={(entry) => set(key, entry)} />
        ))}
      </div>

      <p className="text-[11px] text-muted">
        Criterion positions define AC-001, AC-002, etc. Existing scenario links must still match the edited criteria.
      </p>
    </fieldset>
  );
}
