import React from 'react';

export default function LoadingSkeleton({ label = 'Loading dashboard' }) {
  return <section className="loading-skeleton" role="status" aria-busy="true" aria-label={label}>
    <p>{label}…</p>
    <div className="skeleton-line" aria-hidden="true" />
    <div className="skeleton-grid" aria-hidden="true">{[1, 2, 3, 4].map(key => <div className="skeleton-card" key={key} />)}</div>
    <div className="skeleton-panel" aria-hidden="true" />
  </section>;
}
