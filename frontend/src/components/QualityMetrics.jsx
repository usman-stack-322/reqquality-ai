import React from 'react';
import { AlertCircle, CheckCircle2, ClipboardCheck, Link2, Link2Off } from 'lucide-react';
import { KpiCard, StatusBadge } from './ui';

export default function QualityMetrics({ data }) {
  if (!data) return null;
  const totalCases = data.current_test_case_count || 0;
  const passedCases = data.latest_execution_counts?.Pass || 0;
  const executedCases = (data.latest_execution_counts?.Pass || 0) + (data.latest_execution_counts?.Fail || 0);
  const passRate = executedCases ? `${Math.round((passedCases * 100) / executedCases)}%` : '0%';
  const openBugsTotal = Object.values(data.open_bugs_by_severity || {}).reduce((acc, v) => acc + v, 0);

  return (
    <section className="detail-section integrated-metrics space-y-5" aria-label="Version-aware quality metrics">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="With linked current cases"
          value={data.requirements_with_linked_cases}
          hint={`${data.requirements_with_all_criteria_linked ?? 0} full criteria`}
          icon={Link2}
          tone="success"
        />
        <KpiCard
          label="Without linked cases"
          value={data.requirements_without_linked_cases}
          hint="Need scenario links"
          icon={Link2Off}
          tone={data.requirements_without_linked_cases > 0 ? 'warning' : 'default'}
        />
        <KpiCard
          label="Items needing review"
          value={data.items_needing_review_count}
          hint="Pending SQA / updates"
          icon={ClipboardCheck}
          tone={data.items_needing_review_count > 0 ? 'warning' : 'success'}
        />
        <KpiCard
          label="Open bugs & pass ratio"
          value={openBugsTotal}
          hint={`${passRate} pass (${totalCases} cases)`}
          icon={AlertCircle}
          tone={openBugsTotal > 0 ? 'danger' : 'success'}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs space-y-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">SQA review statuses</h3>
          <ul className="space-y-1.5">
            {Object.entries(data.review_status_counts || {}).map(([key, value]) => (
              <li key={key} className="flex items-center justify-between text-xs">
                <StatusBadge value={key} />
                <strong className="font-semibold text-ink tabular-nums">{value}</strong>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs space-y-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Latest Manual execution</h3>
          <ul className="space-y-1.5">
            {Object.entries(data.latest_execution_counts || {}).map(([key, value]) => (
              <li key={key} className="flex items-center justify-between text-xs">
                <StatusBadge value={key} />
                <strong className="font-semibold text-ink tabular-nums">{value}</strong>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 shadow-xs space-y-2.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">Open bugs by severity</h3>
          <ul className="space-y-1.5">
            {Object.entries(data.open_bugs_by_severity || {}).map(([key, value]) => (
              <li key={key} className="flex items-center justify-between text-xs">
                <StatusBadge value={key} />
                <strong className="font-semibold text-ink tabular-nums">{value}</strong>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="rounded-xl border border-line bg-surface p-4 shadow-xs space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink">Items needing review</h3>
          <span className="text-xs text-muted tabular-nums">{data.items_needing_review_count} flagged</span>
        </div>
        {data.items_needing_review.length ? (
          <ul className="divide-y divide-line">
            {data.items_needing_review.map((r) => (
              <li key={r.id} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                <a className="text-xs font-semibold text-accent hover:underline" href={`#requirement/${r.id}`}>
                  REQ-{r.id}: {r.title}
                </a>
                <span className="text-xs text-muted">
                  v{r.content_revision} · {r.reasons.join('; ')}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-2 text-xs text-success">
            <CheckCircle2 className="size-4" aria-hidden="true" />
            No requirements currently flagged for review.
          </p>
        )}
        {data.items_needing_review_count > data.items_needing_review.length && (
          <p className="text-xs text-muted">
            Showing the first {data.items_needing_review.length} flagged requirements. Use the requirement register for all records.
          </p>
        )}
        <details className="border-t border-line pt-2.5">
          <summary className="cursor-pointer text-xs font-medium text-muted hover:text-ink">
            Metric definitions &amp; measurement scope
          </summary>
          <div className="mt-2 space-y-1.5 text-xs text-muted">
            {Object.entries(data.metric_definitions || {}).map(([key, value]) => (
              <p key={key}>{value}</p>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
}
