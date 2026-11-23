import React from 'react';
import { AlertTriangle, RefreshCw, Sparkles } from 'lucide-react';

export function roleLabel(role) {
  if (role === 'admin') return 'Admin';
  if (role === 'SQA Engineer') return 'SQA Reviewer';
  return role || 'Member';
}

const BADGE_STYLES = {
  // Review & authoring statuses
  draft: 'bg-surface-alt text-muted border-line',
  'ready for review': 'bg-accent-tint text-accent border-accent/25',
  'in review': 'bg-accent-tint text-accent border-accent/30',
  pending: 'bg-warning-tint text-warning border-warning/25',
  'pending review': 'bg-warning-tint text-warning border-warning/25',
  'not reviewed': 'bg-warning-tint text-warning border-warning/25',
  approved: 'bg-success-tint text-success border-success/25',
  'needs revision': 'bg-danger-tint text-danger border-danger/25',

  // Risk & severity & priority
  low: 'bg-success-tint text-success border-success/25',
  medium: 'bg-warning-tint text-warning border-warning/25',
  high: 'bg-danger-tint text-danger border-danger/25',
  critical: 'bg-danger-tint text-danger border-danger/40 font-semibold',
  unscored: 'bg-surface-alt text-muted border-line',
  'not analyzed': 'bg-surface-alt text-muted border-line',

  // Executions
  pass: 'bg-success-tint text-success border-success/25',
  fail: 'bg-danger-tint text-danger border-danger/25',
  blocked: 'bg-warning-tint text-warning border-warning/25',
  'not run': 'bg-surface-alt text-muted border-line',

  // Bugs
  open: 'bg-danger-tint text-danger border-danger/25',
  'in progress': 'bg-accent-tint text-accent border-accent/25',
  'ready for retest': 'bg-warning-tint text-warning border-warning/25',
  closed: 'bg-success-tint text-success border-success/25',

  // Team & roles
  active: 'bg-success-tint text-success border-success/25',
  disabled: 'bg-danger-tint text-danger border-danger/25',
  invited: 'bg-accent-tint text-accent border-accent/25',
  accepted: 'bg-success-tint text-success border-success/25',
  expired: 'bg-warning-tint text-warning border-warning/25',
  revoked: 'bg-danger-tint text-danger border-danger/25',
  admin: 'bg-accent-tint text-accent border-accent/30',
  'sqa admin': 'bg-accent-tint text-accent border-accent/30',
  manager: 'bg-accent-tint text-accent border-accent/25',
  analyst: 'bg-surface-alt text-ink border-line',
  'sqa engineer': 'bg-success-tint text-success border-success/25',
  'sqa reviewer': 'bg-success-tint text-success border-success/25',
};

const DOT_STYLES = {
  approved: 'bg-success',
  pass: 'bg-success',
  closed: 'bg-success',
  active: 'bg-success',
  accepted: 'bg-success',
  low: 'bg-success',
  'sqa engineer': 'bg-success',
  'sqa reviewer': 'bg-success',
  'in review': 'bg-accent',
  'ready for review': 'bg-accent',
  'in progress': 'bg-accent',
  invited: 'bg-accent',
  admin: 'bg-accent',
  'sqa admin': 'bg-accent',
  manager: 'bg-accent',
  pending: 'bg-warning',
  'pending review': 'bg-warning',
  'not reviewed': 'bg-warning',
  'ready for retest': 'bg-warning',
  blocked: 'bg-warning',
  medium: 'bg-warning',
  expired: 'bg-warning',
  'needs revision': 'bg-danger',
  fail: 'bg-danger',
  high: 'bg-danger',
  critical: 'bg-danger',
  open: 'bg-danger',
  disabled: 'bg-danger',
  revoked: 'bg-danger',
};

export function StatusBadge({ value, fallback = 'Unknown', className = '' }) {
  const raw = value || fallback;
  const display = raw === 'Pending' ? 'Not Reviewed' : raw;
  const key = String(raw).trim().toLowerCase();
  const tone = BADGE_STYLES[key] || 'bg-surface-alt text-muted border-line';
  const dot = DOT_STYLES[key] || 'bg-muted';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${tone} ${className}`}>
      <span className={`size-1.5 rounded-full shrink-0 ${dot}`} aria-hidden="true" />
      {display}
    </span>
  );
}

export function KpiCard({ label, value, hint, icon: IconComponent, tone = 'default', onClick }) {
  const toneWrap = tone === 'danger'
    ? 'border-danger/25 bg-surface'
    : tone === 'warning'
      ? 'border-warning/25 bg-surface'
      : tone === 'success'
        ? 'border-success/25 bg-surface'
        : 'border-line bg-surface';
  const iconTone = tone === 'danger'
    ? 'bg-danger-tint text-danger'
    : tone === 'warning'
      ? 'bg-warning-tint text-warning'
      : tone === 'success'
        ? 'bg-success-tint text-success'
        : 'bg-accent-tint text-accent';
  const valueTone = tone === 'danger' ? 'text-danger' : tone === 'success' ? 'text-success' : 'text-ink';
  const Tag = onClick ? 'button' : 'article';
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`group flex flex-col justify-between gap-3 rounded-xl border p-4 text-left shadow-xs transition-colors ${toneWrap} ${onClick ? 'cursor-pointer hover:border-accent/50' : ''}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted">{label}</span>
        {IconComponent && (
          <span className={`inline-flex size-8 items-center justify-center rounded-lg ${iconTone}`}>
            <IconComponent className="size-4" aria-hidden="true" />
          </span>
        )}
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <strong className={`text-2xl font-semibold tracking-tight tabular-nums ${valueTone}`}>{value}</strong>
        {hint && <span className="text-xs text-muted truncate">{hint}</span>}
      </div>
    </Tag>
  );
}

export function EmptyState({ icon: IconComponent, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line bg-surface-alt/50 px-6 py-10 text-center">
      {IconComponent && (
        <div className="mb-3 inline-flex size-10 items-center justify-center rounded-xl bg-accent-tint text-accent">
          <IconComponent className="size-5" aria-hidden="true" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1 max-w-md text-xs text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

const GEMINI_CODE_META = {
  quota_exceeded: { label: 'Gemini Quota / Rate Limit', hint: 'Provider quota or rate limit was reached. Wait briefly and retry.' },
  network_error: { label: 'Gemini Network / Timeout', hint: 'The request timed out or could not reach Gemini. Your text is preserved.' },
  service_unavailable: { label: 'Gemini Service Unavailable', hint: 'Gemini is temporarily unavailable. Retry without re-entering text.' },
  malformed_json: { label: 'Invalid AI Output', hint: 'Gemini returned incomplete structured output. Retry to request a fresh response.' },
  missing_api_key: { label: 'Gemini Not Configured', hint: 'No GEMINI_API_KEY is configured on the backend server.' },
  missing_model: { label: 'Model Not Configured', hint: 'No GEMINI_MODEL is configured on the backend server.' },
  model_unavailable: { label: 'Gemini Model Unavailable', hint: 'The configured Gemini model could not be accessed.' },
  analysis_in_progress: { label: 'Analysis In Progress', hint: 'Another analysis request for this exact input is already running.' },
  stale_analysis: { label: 'Context Changed', hint: 'Requirement or project context changed during analysis. Reload and retry.' },
};

export function GeminiErrorBanner({ error, code, onRetry, busy = false, retryLabel = 'Retry AI Analysis' }) {
  if (!error) return null;
  const meta = (code && GEMINI_CODE_META[code]) || {
    label: 'AI Analysis Error',
    hint: 'Your input and saved records are preserved. No fallback data was fabricated.',
  };
  return (
    <div className="rounded-xl border border-danger/35 bg-danger-tint p-4 text-sm text-danger" role="alert">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3 min-w-0">
          <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface text-danger border border-danger/25">
            <AlertTriangle className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-md bg-surface px-2 py-0.5 text-xs font-semibold text-danger border border-danger/25">
                <Sparkles className="size-3" aria-hidden="true" />
                {meta.label}
              </span>
              {code && <code className="rounded bg-surface/80 px-1.5 py-0.5 text-[11px] font-mono text-danger border border-danger/20">{code}</code>}
            </div>
            <p className="font-medium text-ink break-words">{error}</p>
            <p className="text-xs text-muted">{meta.hint}</p>
          </div>
        </div>
        {onRetry && (
          <button
            type="button"
            disabled={busy}
            onClick={onRetry}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-danger/35 bg-surface px-3 py-2 text-xs font-semibold text-danger hover:bg-surface-alt disabled:opacity-50"
          >
            <RefreshCw className={`size-3.5 ${busy ? 'animate-spin' : ''}`} aria-hidden="true" />
            {busy ? 'Retrying…' : retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="flex flex-col gap-4 border-b border-line pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-1 min-w-0">
        {eyebrow && <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">{eyebrow}</p>}
        <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-[1.65rem]">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2.5 shrink-0">{actions}</div>}
    </div>
  );
}

export const inputClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

export const buttonPrimaryClass =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-accent-strong px-3.5 py-2 text-xs font-semibold text-on-accent shadow-xs transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-55';

export const buttonSecondaryClass =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-surface px-3.5 py-2 text-xs font-semibold text-ink transition hover:bg-surface-alt disabled:cursor-not-allowed disabled:opacity-55';

export const buttonSoftAccentClass =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-accent/25 bg-accent-tint px-3.5 py-2 text-xs font-semibold text-accent transition hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-55';
