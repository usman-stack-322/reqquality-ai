import React from 'react';

const SOURCE_LABELS = {
  original: 'Original',
  rule_based: 'Rule-based',
  ai_suggestion: 'AI Suggestion',
  ai_assumption: 'Assumption',
  confirmed: 'Confirmed',
};

export default function SourceBadges({ source = 'original', needsConfirmation = false, confirmed = false }) {
  const badges = [[source, SOURCE_LABELS[source] || 'Original']];
  if (confirmed && source !== 'confirmed') badges.push(['confirmed', 'Confirmed']);
  if (needsConfirmation && !confirmed) badges.push(['needs-confirmation', 'Needs Confirmation']);

  return (
    <span className="source-badges">
      {badges.map(([kind, label]) => (
        <span className={`content-badge badge-${kind}`} key={kind}>{label}</span>
      ))}
    </span>
  );
}