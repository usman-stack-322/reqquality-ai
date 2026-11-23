import React from 'react';

const SOURCE_LABELS = {
  original: 'Original',
  rule_based: 'Historical analysis',
  ai_suggestion: 'AI Suggestion',
  ai_assumption: 'Assumption',
  confirmed: 'Confirmed',
};

const TONES = {
  original: 'bg-surface-alt text-ink border-line',
  rule_based: 'bg-surface-alt text-muted border-line',
  ai_suggestion: 'bg-accent-tint text-accent border-accent/25',
  ai_assumption: 'bg-warning-tint text-warning border-warning/25',
  confirmed: 'bg-success-tint text-success border-success/25',
  'needs-confirmation': 'bg-warning-tint text-warning border-warning/30',
};

export default function SourceBadges({ source = 'original', needsConfirmation = false, confirmed = false }) {
  const badges = [[source, SOURCE_LABELS[source] || 'Original']];
  if (confirmed && !needsConfirmation && source !== 'confirmed') badges.push(['confirmed', 'Confirmed']);
  if (needsConfirmation) badges.push(['needs-confirmation', 'Needs Confirmation']);

  return (
    <span className="source-badges inline-flex flex-wrap items-center gap-1.5">
      {badges.map(([kind, label]) => (
        <span
          className={`content-badge badge-${kind} inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${TONES[kind] || TONES.original}`}
          key={kind}
        >
          {label}
        </span>
      ))}
    </span>
  );
}
