import React from 'react';

export default function LoadingSkeleton({ label = 'Loading dashboard' }) {
  return (
    <section className="loading-skeleton space-y-5 rounded-xl border border-line bg-surface p-6" role="status" aria-busy="true" aria-label={label}>
      <div className="flex items-center gap-3">
        <span className="size-2.5 rounded-full bg-accent animate-pulse" aria-hidden="true" />
        <p className="text-sm font-medium text-muted">{label}…</p>
      </div>
      <div className="skeleton-line h-4 w-1/3 rounded-md bg-surface-alt animate-pulse" aria-hidden="true" />
      <div className="skeleton-grid grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
        {[1, 2, 3, 4].map((key) => (
          <div className="skeleton-card h-24 rounded-xl border border-line bg-surface-alt animate-pulse" key={key} />
        ))}
      </div>
      <div className="skeleton-panel h-48 rounded-xl border border-line bg-surface-alt animate-pulse" aria-hidden="true" />
    </section>
  );
}
