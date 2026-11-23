import React from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  Check,
  ClipboardCheck,
  Clock,
  FileBarChart2,
  FileText,
  FolderKanban,
  LayoutDashboard,
  Link2,
  LogOut,
  Mail,
  Plus,
  Search,
  Settings,
  Users,
} from 'lucide-react';
import { EmptyState, StatusBadge } from './ui';

const LUCIDE_MAP = {
  dashboard: LayoutDashboard,
  projects: FolderKanban,
  requirements: FileText,
  reviews: ClipboardCheck,
  team: Users,
  invitations: Mail,
  traceability: Link2,
  reports: FileBarChart2,
  activity: Activity,
  settings: Settings,
  logout: LogOut,
  search: Search,
  bell: Bell,
  arrow: ArrowRight,
  plus: Plus,
  alert: AlertTriangle,
  check: Check,
  clock: Clock,
};

export function Icon({ name, size = 18, className = '' }) {
  const Component = LUCIDE_MAP[name] || LayoutDashboard;
  return <Component size={size} className={className} aria-hidden="true" />;
}

export function Badge({ value, risk = false }) {
  return <StatusBadge value={value} fallback={risk ? 'Unscored' : 'Not Reviewed'} />;
}

export function formatDate(value) {
  if (!value) return 'Not recorded';
  const normalized = /(?:Z|[+-]\d{2}(?::?\d{2})?)$/i.test(value) ? value.replace(' ', 'T') : `${value.replace(' ', 'T')}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function Panel({ title, subtitle, action, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 shadow-xs min-w-0 ${className}`}>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }) {
  return <EmptyState title={children} />;
}

export function Distribution({ items, total, onSelect, risk = false }) {
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <button
          type="button"
          className="block w-full rounded-lg border border-transparent p-2 text-left transition hover:border-line hover:bg-surface-alt/60"
          key={item.value}
          onClick={() => onSelect(item.value)}
          aria-label={`${item.label}: ${item.count}, ${item.percent}%`}
        >
          <div className="mb-1.5 flex items-center justify-between gap-2 text-xs">
            <Badge value={item.label} risk={risk} />
            <span className="tabular-nums text-muted">
              <strong className="font-semibold text-ink">{item.count}</strong> · {item.percent}%
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-alt">
            <div
              className="h-full rounded-full bg-accent-strong transition-all"
              style={{ width: `${item.percent}%` }}
            />
          </div>
        </button>
      ))}
      {!total && <Empty>No requirements match these filters.</Empty>}
    </div>
  );
}

export function RequirementTable({ rows, onAssign, pending = false }) {
  if (!rows.length) return <Empty>{pending ? 'No pending reviews.' : 'No requirements match this view.'}</Empty>;
  return (
    <div
      className="table-wrapper"
      tabIndex={0}
      role="region"
      aria-label={pending ? 'SQA Review Queue table' : 'Requirements table'}
    >
      <table className="min-w-[780px] text-left text-xs">
        <caption className="visually-hidden">{pending ? 'SQA Review Queue' : 'Requirements register'}</caption>
        <thead>
          <tr className="border-b border-line text-[11px] font-semibold uppercase tracking-wider text-muted">
            <th scope="col" className="px-4 py-3">Requirement</th>
            <th scope="col" className="px-4 py-3">Project / Type</th>
            {pending && <th scope="col" className="px-4 py-3">Submitted by</th>}
            <th scope="col" className="px-4 py-3">Risk</th>
            <th scope="col" className="px-4 py-3">Review status</th>
            <th scope="col" className="px-4 py-3">Assigned reviewer</th>
            <th scope="col" className="px-4 py-3">{pending ? 'Submitted' : 'Updated'}</th>
            <th scope="col" className="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-surface-alt/50 transition-colors">
              <td className="px-4 py-3 max-w-xs">
                <a className="block font-semibold text-ink hover:text-accent hover:underline" href={`#admin/requirement/${row.id}`}>
                  <span className="mr-1.5 font-mono text-[11px] text-muted">REQ-{row.id}</span>
                  {row.title}
                </a>
                {row.attention_reasons?.length > 0 && (
                  <span className="mt-1 block text-[11px] text-warning">{row.attention_reasons.join(' · ')}</span>
                )}
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <span className="block font-medium text-ink">{row.project}</span>
                <span className="text-[11px] text-muted">{row.requirement_type}</span>
              </td>
              {pending && <td className="px-4 py-3 whitespace-nowrap text-muted">{row.submitted_by || 'Not recorded'}</td>}
              <td className="px-4 py-3 whitespace-nowrap"><Badge value={row.risk_level} risk /></td>
              <td className="px-4 py-3 whitespace-nowrap"><Badge value={row.review_status} /></td>
              <td className="px-4 py-3 whitespace-nowrap">
                {row.assigned_reviewer ? (
                  <span className="font-medium text-ink">{row.assigned_reviewer}</span>
                ) : (
                  <span className="text-muted">Unassigned</span>
                )}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-muted tabular-nums">
                {formatDate(pending ? row.created_at : row.updated_at || row.created_at)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-right">
                <div className="inline-flex items-center justify-end gap-2">
                  <a
                    className="rounded-md border border-line bg-surface px-2.5 py-1 text-[11px] font-medium text-ink hover:border-accent/50 hover:text-accent"
                    href={`#admin/requirement/${row.id}`}
                  >
                    {pending ? 'View Details' : 'View'}
                  </a>
                  <button
                    type="button"
                    className="rounded-md border border-line bg-surface-alt px-2.5 py-1 text-[11px] font-medium text-ink hover:border-accent/50"
                    onClick={() => onAssign(row)}
                  >
                    {row.assigned_reviewer_user_id ? 'Reassign' : 'Assign'}
                  </button>
                  {!pending && (
                    <a
                      className="rounded-md bg-accent-tint px-2.5 py-1 text-[11px] font-semibold text-accent hover:underline"
                      href={`#admin/requirement/${row.id}?review=1`}
                    >
                      Review
                    </a>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ActivityList({ items }) {
  if (!items.length) {
    return <Empty>No activity recorded yet. New requirement, review, invitation and management actions will appear here.</Empty>;
  }
  return (
    <ol className="divide-y divide-line">
      {items.map((event) => (
        <li key={event.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
          <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent-tint text-accent">
            <Icon
              name={event.entity_type === 'requirement' ? 'reviews' : event.entity_type === 'invitation' ? 'invitations' : 'team'}
              size={14}
            />
          </span>
          <div className="min-w-0 flex-1 space-y-0.5 text-xs">
            <p className="text-ink">
              <strong className="font-semibold">{event.actor_name}</strong>{' '}
              <span className="text-muted">{event.summary}</span>
            </p>
            <p className="text-[11px] text-muted">
              {event.entity_type === 'requirement' ? (
                <a className="font-medium text-accent hover:underline" href={`#admin/requirement/${event.entity_id}`}>
                  REQ-{event.entity_id}
                </a>
              ) : (
                <span>
                  {event.entity_type} {event.entity_id}
                </span>
              )}{' '}
              · {formatDate(event.created_at)} ·{' '}
              {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
